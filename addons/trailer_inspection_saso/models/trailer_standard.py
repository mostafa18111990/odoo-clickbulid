from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrailerInspectionStandard(models.Model):
    _name = "trailer.inspection.standard"
    _description = "Trailer Inspection Standard or Regulation"
    _order = "code, edition desc"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    title_ar = fields.Char(string="Arabic Title", required=True)
    title_en = fields.Char(string="English Title", required=True)
    edition = fields.Char(required=True)
    authority = fields.Selection(
        [
            ("saso", "SASO"),
            ("gso", "GSO"),
            ("iso", "ISO"),
            ("internal", "Internal Method"),
        ],
        required=True,
        default="saso",
    )
    document_type = fields.Selection(
        [
            ("technical_regulation", "Technical Regulation"),
            ("standard", "Standard"),
            ("guideline", "Guideline"),
            ("inspection_method", "Inspection Method"),
        ],
        required=True,
        default="standard",
    )
    publication_date = fields.Date()
    effective_date = fields.Date()
    status = fields.Selection(
        [("current", "Current"), ("superseded", "Superseded"), ("reference", "Reference Only")],
        required=True,
        default="current",
    )
    superseded_by_id = fields.Many2one("trailer.inspection.standard", ondelete="restrict")
    source_url = fields.Char()
    document = fields.Binary(attachment=True)
    document_filename = fields.Char()
    notes = fields.Text()
    active = fields.Boolean(default=True)

    _code_edition_unique = models.Constraint(
        "UNIQUE(code, edition)",
        "The standard code and edition must be unique.",
    )

    @api.constrains("status", "superseded_by_id")
    def _check_superseded_reference(self):
        for record in self:
            if record.status == "superseded" and not record.superseded_by_id:
                raise ValidationError("A superseded standard must identify its replacement.")
            if record.superseded_by_id == record:
                raise ValidationError("A standard cannot supersede itself.")


class TrailerInspectionSection(models.Model):
    _name = "trailer.inspection.section"
    _description = "Trailer Inspection Requirement Section"
    _order = "sequence, code"

    name = fields.Char(required=True)
    name_ar = fields.Char(string="Arabic Name", required=True)
    name_en = fields.Char(string="English Name", required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "The section code must be unique.")


class TrailerInspectionRequirement(models.Model):
    _name = "trailer.inspection.requirement"
    _description = "Trailer Inspection Requirement"
    _order = "section_id, sequence, clause_ref"

    name = fields.Char(required=True, index=True)
    name_ar = fields.Char(string="Arabic Name", required=True)
    name_en = fields.Char(string="English Name", required=True)
    code = fields.Char(required=True, index=True)
    clause_ref = fields.Char(string="Clause", required=True)
    section_id = fields.Many2one("trailer.inspection.section", required=True, ondelete="restrict")
    standard_id = fields.Many2one("trailer.inspection.standard", required=True, ondelete="restrict")
    criterion_ar = fields.Text(string="Arabic Acceptance Criterion", required=True)
    criterion_en = fields.Text(string="English Acceptance Criterion", required=True)
    sequence = fields.Integer(default=10)
    criticality = fields.Selection(
        [("minor", "Minor"), ("major", "Major"), ("critical", "Critical")],
        required=True,
        default="major",
    )
    response_type = fields.Selection(
        [("choice", "Yes / No / N/A"), ("numeric", "Numeric Measurement"), ("text", "Text Evidence")],
        required=True,
        default="choice",
    )
    minimum_value = fields.Float()
    maximum_value = fields.Float()
    unit = fields.Char()
    applies_o1 = fields.Boolean(default=True)
    applies_o2 = fields.Boolean(default=True)
    applies_o3 = fields.Boolean(default=True)
    applies_o4 = fields.Boolean(default=True)
    evidence_required = fields.Boolean()
    equipment_required = fields.Boolean()
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "The requirement code must be unique.")

    @api.constrains("minimum_value", "maximum_value")
    def _check_measurement_range(self):
        for record in self:
            if (
                record.response_type == "numeric"
                and record.minimum_value
                and record.maximum_value
                and record.minimum_value > record.maximum_value
            ):
                raise ValidationError("The minimum value cannot exceed the maximum value.")

    def applies_to_category(self, category):
        self.ensure_one()
        return bool(getattr(self, f"applies_{category}", False))
