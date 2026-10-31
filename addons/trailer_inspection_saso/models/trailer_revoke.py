from odoo import fields, models


class TrailerInspectionRevoke(models.TransientModel):
    _name = "trailer.inspection.revoke"
    _description = "Revoke Inspection Report Approval"

    inspection_id = fields.Many2one("trailer.inspection", required=True, readonly=True, ondelete="cascade")
    inspection_name = fields.Char(related="inspection_id.name")
    vin = fields.Char(related="inspection_id.vin")
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        # The inspection re-checks the manager group and the approved state.
        self.inspection_id.action_revoke(self.reason)
        return {"type": "ir.actions.act_window_close"}
