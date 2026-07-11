from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "The equipment code must be unique per company.",
    )

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

    @api.model
    def _cron_deadline_alerts(self):
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
