import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


VIN_ALLOWED_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]+$")
VIN_TRANSLITERATION = {
    **{str(number): number for number in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
VIN_POSITION_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
VIN_YEAR_CODES = {
    2005: "5", 2006: "6", 2007: "7", 2008: "8", 2009: "9",
    2010: "A", 2011: "B", 2012: "C", 2013: "D", 2014: "E",
    2015: "F", 2016: "G", 2017: "H", 2018: "J", 2019: "K",
    2020: "L", 2021: "M", 2022: "N", 2023: "P", 2024: "R",
    2025: "S", 2026: "T", 2027: "V", 2028: "W", 2029: "X",
    2030: "Y", 2031: "1", 2032: "2", 2033: "3", 2034: "4",
    2035: "5", 2036: "6", 2037: "7", 2038: "8",
}


def calculate_vin_check_digit(vin):
    normalized = (vin or "").replace(" ", "").upper()
    if len(normalized) != 17 or not VIN_ALLOWED_PATTERN.fullmatch(normalized):
        raise ValueError("VIN must contain 17 permitted characters")
    total = sum(
        VIN_TRANSLITERATION[character] * VIN_POSITION_WEIGHTS[position]
        for position, character in enumerate(normalized)
        if position != 8
    )
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


class TrailerVinProfile(models.Model):
    _name = "trailer.vin.profile"
    _description = "Trailer VIN Manufacturer Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "manufacturer_id, name"

    name = fields.Char(required=True, tracking=True)
    manufacturer_id = fields.Many2one("res.partner", required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    wmi = fields.Char(string="World Manufacturer Identifier (WMI)", required=True, size=3, tracking=True)
    vds = fields.Char(string="Vehicle Descriptor Section (VDS)", required=True, size=5, tracking=True)
    plant_code = fields.Char(string="Plant Code", required=True, size=1, tracking=True)
    low_volume = fields.Boolean(string="Low-Volume Manufacturer", tracking=True)
    low_volume_identifier = fields.Char(
        string="Low-Volume Identifier", size=3,
        help="Assigned manufacturer identifier used in VIS positions 3-5 for manufacturers producing fewer than 1000 vehicles of the type annually.",
    )
    wmi_certificate_number = fields.Char(string="WMI Certificate Number")
    wmi_certificate = fields.Binary(attachment=True)
    wmi_certificate_filename = fields.Char()
    assignment_authority_confirmed = fields.Boolean(
        string="VIN Assignment Authority Confirmed",
        help="Confirm that the organization is authorized by the manufacturer to assign VINs using this controlled profile.",
        tracking=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved"), ("archived", "Archived")],
        required=True,
        default="draft",
        tracking=True,
    )
    approved_by = fields.Many2one("res.users", string="Profile Approved By", readonly=True, copy=False)
    approved_on = fields.Datetime(string="Profile Approved On", readonly=True, copy=False)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _profile_unique = models.Constraint(
        "UNIQUE(company_id, wmi, vds, plant_code)",
        "The WMI, VDS and plant-code combination must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for key in ("wmi", "vds", "plant_code", "low_volume_identifier"):
                if vals.get(key):
                    vals[key] = vals[key].replace(" ", "").upper()
        return super().create(vals_list)

    def write(self, vals):
        controlled_fields = {"manufacturer_id", "company_id", "wmi", "vds", "plant_code", "low_volume", "low_volume_identifier", "wmi_certificate_number", "wmi_certificate", "assignment_authority_confirmed"}
        if controlled_fields.intersection(vals) and self.filtered(lambda record: record.state == "approved"):
            raise UserError(_("Reset the approved VIN profile to draft before changing controlled fields."))
        for key in ("wmi", "vds", "plant_code", "low_volume_identifier"):
            if vals.get(key):
                vals[key] = vals[key].replace(" ", "").upper()
        return super().write(vals)

    @api.constrains("wmi", "vds", "plant_code", "low_volume", "low_volume_identifier")
    def _check_profile_codes(self):
        for record in self:
            for label, value, length in (
                (_("WMI"), record.wmi, 3), (_("VDS"), record.vds, 5),
                (_("plant code"), record.plant_code, 1),
            ):
                if len(value or "") != length or not VIN_ALLOWED_PATTERN.fullmatch(value or ""):
                    raise ValidationError(_("%(label)s must contain exactly %(length)s permitted VIN characters.", label=label, length=length))
            if record.low_volume:
                identifier = record.low_volume_identifier or ""
                if len(identifier) != 3 or not VIN_ALLOWED_PATTERN.fullmatch(identifier):
                    raise ValidationError(_("Low-volume identifier must contain exactly three permitted VIN characters."))
                if not identifier[-1].isdigit():
                    raise ValidationError(_("The last low-volume identifier character must be numeric so the final four VIN characters remain numeric."))

    def _next_serial(self, model_year):
        self.ensure_one()
        sequence_model = self.env["trailer.vin.sequence"].sudo()
        sequence = sequence_model.search([("profile_id", "=", self.id), ("model_year", "=", model_year)], limit=1)
        if not sequence:
            sequence = sequence_model.create({"profile_id": self.id, "model_year": model_year, "next_number": 1})
        self.env.cr.execute(
            "SELECT next_number FROM trailer_vin_sequence WHERE id = %s FOR UPDATE",
            [sequence.id],
        )
        next_number = self.env.cr.fetchone()[0]
        maximum = 999 if self.low_volume else 999999
        if next_number > maximum:
            raise UserError(_("The VIN serial range for this profile and model year is exhausted."))
        sequence.write({"next_number": next_number + 1})
        return next_number

    def action_approve(self):
        for record in self:
            if not record.wmi_certificate_number or not record.wmi_certificate:
                raise UserError(_("WMI certificate number and attachment are required before profile approval."))
            if not record.assignment_authority_confirmed:
                raise UserError(_("Confirm the authority to assign VINs before profile approval."))
            record.write({"state": "approved", "approved_by": self.env.user.id, "approved_on": fields.Datetime.now()})

    def action_archive(self):
        self.write({"state": "archived", "active": False})

    def action_reset_draft(self):
        self.write({"state": "draft", "active": True, "approved_by": False, "approved_on": False})

    def generate_vin(self, model_year):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("VIN generation requires an approved manufacturer profile."))
        if model_year not in VIN_YEAR_CODES:
            raise UserError(_("Model year must be between 2005 and 2038 according to the attached GSO 1780 table."))
        serial_number = self._next_serial(model_year)
        if self.low_volume:
            vis = f"{VIN_YEAR_CODES[model_year]}{self.plant_code}{self.low_volume_identifier}{serial_number:03d}"
        else:
            vis = f"{VIN_YEAR_CODES[model_year]}{self.plant_code}{serial_number:06d}"
        provisional = f"{self.wmi}{self.vds}0{vis}"
        check_digit = calculate_vin_check_digit(provisional)
        return f"{provisional[:8]}{check_digit}{provisional[9:]}"


class TrailerVinSequence(models.Model):
    _name = "trailer.vin.sequence"
    _description = "Trailer VIN Production Sequence"
    _order = "model_year desc, profile_id"

    profile_id = fields.Many2one("trailer.vin.profile", required=True, ondelete="cascade")
    model_year = fields.Integer(string="Model Year", required=True)
    next_number = fields.Integer(string="Next Serial Number", required=True, default=1)

    _profile_year_unique = models.Constraint(
        "UNIQUE(profile_id, model_year)",
        "Only one VIN sequence is allowed per profile and model year.",
    )

    @api.constrains("next_number")
    def _check_next_number(self):
        if self.filtered(lambda record: record.next_number < 1):
            raise ValidationError(_("The next VIN serial number must be greater than zero."))
