import base64
import csv
import io
import re
import zipfile
from xml.etree import ElementTree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class TrailerQualityDocument(models.Model):
    _name = "trailer.quality.document"
    _description = "Inspection Quality Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code, revision desc"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    document_type = fields.Selection(
        [("procedure", "Procedure"), ("work_instruction", "Work Instruction"), ("form", "Form"), ("policy", "Policy"), ("record", "Quality Record")],
        required=True,
        default="procedure",
    )
    revision = fields.Char(required=True, default="01")
    state = fields.Selection([("draft", "Draft"), ("review", "Under Review"), ("approved", "Approved"), ("obsolete", "Obsolete")], default="draft", tracking=True)
    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    reviewer_id = fields.Many2one("res.users")
    effective_date = fields.Date()
    next_review_date = fields.Date()
    attachment = fields.Binary(attachment=True)
    filename = fields.Char()
    notes = fields.Text()
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    _code_revision_unique = models.Constraint("UNIQUE(code, revision, company_id)", "Document code and revision must be unique per company.")

    def action_submit(self):
        self.write({"state": "review"})

    def action_approve(self):
        for record in self:
            if record.reviewer_id == record.owner_id:
                raise UserError(_("The document reviewer must be independent from its owner."))
            if not record.attachment:
                raise UserError(_("Attach the controlled document before approval."))
            record.write({"state": "approved", "effective_date": record.effective_date or fields.Date.today()})

    def action_obsolete(self):
        self.write({"state": "obsolete"})


class TrailerQualityComplaint(models.Model):
    _name = "trailer.quality.complaint"
    _description = "Inspection Complaint or Appeal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "received_date desc, id desc"

    name = fields.Char(default="New", required=True, readonly=True, copy=False)
    complaint_type = fields.Selection([("complaint", "Complaint"), ("appeal", "Appeal")], required=True, default="complaint")
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    inspection_id = fields.Many2one("trailer.inspection", ondelete="set null", tracking=True)
    received_date = fields.Date(required=True, default=fields.Date.today)
    description = fields.Text(required=True)
    assigned_to = fields.Many2one("res.users", tracking=True)
    investigation = fields.Text()
    resolution = fields.Text()
    due_date = fields.Date()
    closed_on = fields.Date(readonly=True)
    state = fields.Selection([("new", "New"), ("investigating", "Investigating"), ("resolved", "Resolved"), ("closed", "Closed")], default="new", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("trailer.quality.complaint") or "New"
        return super().create(vals_list)

    def action_investigate(self):
        self.write({"state": "investigating"})

    def action_resolve(self):
        for record in self:
            if not record.investigation or not record.resolution:
                raise UserError(_("Investigation and resolution are required."))
            record.state = "resolved"

    def action_close(self):
        self.write({"state": "closed", "closed_on": fields.Date.today()})


class TrailerInspectionImport(models.TransientModel):
    _name = "trailer.inspection.import"
    _description = "Import Trailer Inspection Data"

    file = fields.Binary(required=True)
    filename = fields.Char(required=True)

    def _rows_from_csv(self, content):
        text = content.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))

    def _rows_from_xlsx(self, content):
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.itertext()) for node in root.findall("x:si", namespace)]
            sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            table = []
            for row in sheet.findall(".//x:row", namespace):
                values = {}
                for cell in row.findall("x:c", namespace):
                    reference = cell.get("r", "A1")
                    letters = re.match(r"[A-Z]+", reference).group(0)
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter) - 64
                    column -= 1
                    value_node = cell.find("x:v", namespace)
                    value = value_node.text if value_node is not None else ""
                    if cell.get("t") == "s" and value:
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        inline = cell.find("x:is", namespace)
                        value = "".join(inline.itertext()) if inline is not None else ""
                    values[column] = value
                if values:
                    width = max(values) + 1
                    table.append([values.get(index, "") for index in range(width)])
        if not table:
            return []
        headers = table[0]
        return [dict(zip(headers, row)) for row in table[1:]]

    def action_import(self):
        self.ensure_one()
        content = base64.b64decode(self.file)
        extension = (self.filename.rsplit(".", 1)[-1] or "").lower()
        if extension == "csv":
            rows = self._rows_from_csv(content)
        elif extension == "xlsx":
            rows = self._rows_from_xlsx(content)
        else:
            raise UserError(_("Upload a UTF-8 CSV or XLSX file."))
        created = self.env["trailer.inspection"]
        for number, row in enumerate(rows, start=2):
            try:
                values = {
                    "partner_id": int(row["partner_id"]),
                    "inspection_location": row["inspection_location"],
                    "inspector_id": int(row["inspector_id"]),
                    "product_description": row["product_description"],
                    "trailer_type": row.get("trailer_type") or "trailer",
                    "category": row.get("category") or "o3",
                    "vin": row["vin"],
                    "manufacturer_name": row["manufacturer_name"],
                    "model_name": row.get("model_name"),
                    "gross_weight_kg": float(row.get("gross_weight_kg") or 0),
                }
                created |= self.env["trailer.inspection"].create(values)
            except (KeyError, TypeError, ValueError) as error:
                raise ValidationError(_("Invalid import row %(row)s: %(error)s", row=number, error=str(error))) from error
        return {"type": "ir.actions.act_window", "res_model": "trailer.inspection", "view_mode": "list,form", "domain": [("id", "in", created.ids)]}
