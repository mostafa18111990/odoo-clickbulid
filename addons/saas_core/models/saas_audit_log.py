from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)

AUDIT_ACTIONS = [
    ('create', 'Create'), ('write', 'Update'), ('unlink', 'Delete'),
    ('login', 'Login'), ('logout', 'Logout'), ('export', 'Export'),
    ('migrate', 'Migration'), ('provision', 'Provision'), ('suspend', 'Suspend'),
    ('activate', 'Activate'), ('cancel', 'Cancel'), ('archive', 'Archive'),
    ('delete', 'Delete Tenant'), ('payment', 'Payment Action'),
    ('backup', 'Backup Action'), ('restore', 'Restore Action'),
    ('api_call', 'API Call'), ('security', 'Security Event'),
]


class SaasAuditLog(models.Model):
    _name = 'saas.audit.log'
    _description = 'SaaS Audit Log'
    _order = 'create_date desc'
    _rec_name = 'description'

    model = fields.Char(string='Model', required=True, index=True)
    record_id = fields.Integer(string='Record ID', index=True)
    action = fields.Selection(selection=AUDIT_ACTIONS, string='Action', required=True, index=True)
    description = fields.Text(string='Description', required=True)
    user_id = fields.Many2one('res.users', string='User', readonly=True, index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='set null', index=True)
    old_values = fields.Text(string='Old Values (JSON)', readonly=True)
    new_values = fields.Text(string='New Values (JSON)', readonly=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    user_agent = fields.Char(string='User Agent', readonly=True)
    request_path = fields.Char(string='Request Path', readonly=True)
    severity = fields.Selection(
        selection=[('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical')],
        string='Severity', default='info', index=True)

    @api.model
    def log_action(self, model, action, description, record_id=None, user_id=None,
                   tenant_id=None, old_values=None, new_values=None, severity='info', ip_address=None):
        try:
            if not ip_address:
                try:
                    from odoo.http import request as http_req
                    if http_req:
                        ip_address = (http_req.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                                      or http_req.httprequest.remote_addr)
                except Exception:
                    pass
            return self.sudo().create({
                'model': model, 'record_id': record_id or 0, 'action': action,
                'description': description, 'user_id': user_id or self.env.uid,
                'tenant_id': tenant_id,
                'old_values': json.dumps(old_values, default=str) if old_values else False,
                'new_values': json.dumps(new_values, default=str) if new_values else False,
                'severity': severity, 'ip_address': ip_address,
            })
        except Exception as e:
            _logger.error('AuditLog.log_action failed: %s', e)
            return self.browse()

    def write(self, vals):
        raise UserError('Audit logs are immutable and cannot be modified.')

    def unlink(self):
        raise UserError('Audit logs cannot be deleted.')
