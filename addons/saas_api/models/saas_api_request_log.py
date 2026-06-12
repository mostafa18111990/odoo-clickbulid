from odoo import models, fields


class SaasApiRequestLog(models.Model):
    _name = 'saas.api.request.log'
    _description = 'API Request Log'
    _order = 'create_date desc'

    token_id = fields.Many2one('saas.api.token', string='Token',
                               ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='set null', index=True)
    endpoint = fields.Char(string='Endpoint', index=True)
    method = fields.Char(string='HTTP Method')
    status_code = fields.Integer(string='Status', index=True)
    response_time_ms = fields.Integer(string='Response Time (ms)')
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')
    error_message = fields.Text(string='Error')
