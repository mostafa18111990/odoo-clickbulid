from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# Set only by an inspection manager: a temporary, documented permission to
# keep using an instrument whose calibration has lapsed.
EXCEPTION_FIELDS = ("expired_use_allowed_until", "expired_use_reason")


class TrailerInspectionEquipment(models.Model):
    _name = "trailer.inspection.equipment"
    _description = "Trailer Inspection Measuring Equipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    serial_number = fields.Char(required=True, tracking=True)
    equipment_type = fields.Selection(
        [
            ("dimension", "Dimension"),
            ("weight", "Weight"),
            ("electrical", "Electrical"),
            ("brake", "Brake"),
            ("lighting", "Lighting"),
            ("other", "Other"),
        ],
        required=True,
        default="dimension",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    calibration_certificate = fields.Binary(attachment=True)
    calibration_filename = fields.Char()
    calibrated_on = fields.Date(tracking=True)
    calibration_due_date = fields.Date(required=True, tracking=True)
    calibration_status = fields.Selection(
        [("valid", "Valid"), ("due_soon", "Due Soon"), ("expired", "Expired")],
        compute="_compute_calibration_status",
        store=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()
    expired_use_allowed_until = fields.Date(
        string="Use Despite Expired Calibration Until", tracking=True, copy=False,
        help="Inspection manager's temporary permission to keep using this instrument after its "
             "calibration lapsed. It ends on this date; a reason is mandatory.")
    expired_use_reason = fields.Text(string="Reason for Using Uncalibrated Equipment", tracking=True, copy=False)
    expired_use_approved_by = fields.Many2one("res.users", string="Exception Approved By", readonly=True, copy=False, tracking=True)
    expired_use_approved_on = fields.Datetime(string="Exception Approved On", readonly=True, copy=False)
    usable_for_inspection = fields.Boolean(
        compute="_compute_usable_for_inspection", search="_search_usable_for_inspection")

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "The equipment code must be unique per company.",
    )

    @api.depends("calibration_due_date", "expired_use_allowed_until")
    def _compute_usable_for_inspection(self):
        for record in self:
            record.usable_for_inspection = not record._is_blocked_for_use()

    def _search_usable_for_inspection(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on usable equipment."))
        today = fields.Date.context_today(self)
        usable = ["|", ("calibration_due_date", ">=", today), ("expired_use_allowed_until", ">=", today)]
        return usable if (operator == "=") == value else ["!"] + usable

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(name) for name in EXCEPTION_FIELDS):
                self._check_exception_rights()
                vals.update(expired_use_approved_by=self.env.user.id,
                            expired_use_approved_on=fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if "expired_use_approved_by" in vals or "expired_use_approved_on" in vals:
            if not self.env.su:
                raise AccessError(_("The exception approval is recorded automatically."))
        if any(name in vals for name in EXCEPTION_FIELDS):
            self._check_exception_rights()
            granted = vals.get("expired_use_allowed_until", True)
            vals.update(
                expired_use_approved_by=self.env.user.id if granted else False,
                expired_use_approved_on=fields.Datetime.now() if granted else False,
            )
        return super().write(vals)

    def _check_exception_rights(self):
        if not self.env.su and not self.env.user.has_group("trailer_inspection_saso.group_trailer_manager"):
            raise AccessError(_("Only an inspection manager can allow the use of uncalibrated equipment."))

    @api.constrains("expired_use_allowed_until", "expired_use_reason")
    def _check_exception_reason(self):
        for record in self:
            if record.expired_use_allowed_until and not (record.expired_use_reason or "").strip():
                raise ValidationError(_("State why this uncalibrated equipment may still be used."))

    @api.depends("calibration_due_date")
    def _compute_calibration_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.calibration_due_date or record.calibration_due_date < today:
                record.calibration_status = "expired"
            elif (record.calibration_due_date - today).days <= 30:
                record.calibration_status = "due_soon"
            else:
                record.calibration_status = "valid"

    @api.constrains("calibrated_on", "calibration_due_date")
    def _check_calibration_dates(self):
        for record in self:
            if record.calibrated_on and record.calibration_due_date <= record.calibrated_on:
                raise ValidationError("Calibration due date must be after the calibration date.")

    def _is_calibration_expired(self, on_date=None):
        """Decided from the due date itself: the stored status is only as
        fresh as the last refresh, and time passes without any write."""
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        return not self.calibration_due_date or self.calibration_due_date < on_date

    def _is_blocked_for_use(self, on_date=None):
        """Expired, and not covered by a manager's exception on that date."""
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        if not self._is_calibration_expired(on_date):
            return False
        return not (self.expired_use_allowed_until and self.expired_use_allowed_until >= on_date)

    @api.model
    def _refresh_date_dependent_states(self):
        """Stored statuses that depend on today's date go stale overnight.

        Marking the due dates modified recomputes every status derived from
        them, including the copies stored on equipment-use records.
        """
        equipment = self.with_context(active_test=False).search([])
        equipment.modified(["calibration_due_date"])
        authorizations = self.env["trailer.inspector.authorization"].search([])
        authorizations.modified(["valid_from"])
        self.env.flush_all()

    @api.model
    def _cron_deadline_alerts(self):
        self._refresh_date_dependent_states()
        today = fields.Date.today()
        manager_group = self.env.ref("trailer_inspection_saso.group_trailer_manager")
        managers = self.env["res.users"].search([("all_group_ids", "in", manager_group.id)])
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        equipment_model = self.env["ir.model"]._get(self._name)
        equipment = self.search([
            ("active", "=", True), ("calibration_due_date", "<=", fields.Date.add(today, days=30))
        ])
        for item in equipment:
            for user in managers.filtered(lambda record: item.company_id in record.company_ids):
                domain = [("res_model_id", "=", equipment_model.id), ("res_id", "=", item.id), ("user_id", "=", user.id), ("activity_type_id", "=", activity_type.id)]
                if not self.env["mail.activity"].search_count(domain):
                    self.env["mail.activity"].create({
                        "res_model_id": equipment_model.id, "res_id": item.id,
                        "activity_type_id": activity_type.id, "user_id": user.id,
                        "summary": _("Calibration deadline: %s", item.name),
                        "date_deadline": item.calibration_due_date,
                    })


class TrailerInspectorAuthorization(models.Model):
    _name = "trailer.inspector.authorization"
    _description = "Trailer Inspector Authorization"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_to desc, user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    authorization_number = fields.Char(required=True, tracking=True)
    valid_from = fields.Date(required=True, tracking=True)
    valid_to = fields.Date(required=True, tracking=True)
    scope_o1 = fields.Boolean(default=True)
    scope_o2 = fields.Boolean(default=True)
    scope_o3 = fields.Boolean(default=True)
    scope_o4 = fields.Boolean(default=True)
    certificate = fields.Binary(attachment=True)
    certificate_filename = fields.Char()
    state = fields.Selection(
        [("active", "Active"), ("suspended", "Suspended"), ("expired", "Expired")],
        compute="_compute_state",
        store=True,
    )
    notes = fields.Text()

    @api.depends("valid_from", "valid_to")
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.state = "active" if record.valid_from <= today <= record.valid_to else "expired"

    @api.constrains("valid_from", "valid_to")
    def _check_validity_dates(self):
        for record in self:
            if record.valid_to < record.valid_from:
                raise ValidationError("Authorization end date cannot precede its start date.")

    def authorizes(self, category, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        return (
            self.valid_from <= on_date <= self.valid_to
            and bool(getattr(self, f"scope_{category}", False))
        )
