from odoo import models, fields


class SaasHealthHistory(models.Model):
    _name = 'saas.health.history'
    _description = 'Health Check History Entry'
    _order = 'checked_at desc'

    check_id = fields.Many2one('saas.health.check', string='Check',
                               required=True, ondelete='cascade', index=True)
    status = fields.Selection(
        selection=[('up', 'Up'), ('degraded', 'Degraded'), ('down', 'Down')],
        string='Status', required=True, index=True)
    response_ms = fields.Integer(string='Response (ms)')
    checked_at = fields.Datetime(string='Checked At', default=fields.Datetime.now, index=True)
    error_message = fields.Text(string='Error')
    status_code = fields.Integer(string='HTTP Status')
