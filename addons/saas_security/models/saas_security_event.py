from odoo import models, fields


class SaasSecurityEvent(models.Model):
    _name = 'saas.security.event'
    _description = 'Security Event Audit'
    _order = 'create_date desc'

    event_type = fields.Selection(
        selection=[('brute_force', 'Brute Force Attempt'),
                   ('account_lockout', 'Account Lockout'),
                   ('password_breach', 'Password Breach Detected'),
                   ('suspicious_ip', 'Suspicious IP'),
                   ('2fa_enabled', '2FA Enabled'),
                   ('2fa_disabled', '2FA Disabled'),
                   ('password_changed', 'Password Changed'),
                   ('admin_action', 'Admin Sensitive Action'),
                   ('token_revoked', 'API Token Revoked'),
                   ('other', 'Other')],
        string='Event Type', required=True, index=True)
    severity = fields.Selection(
        selection=[('low', 'Low'), ('medium', 'Medium'),
                   ('high', 'High'), ('critical', 'Critical')],
        string='Severity', default='medium', required=True, index=True)
    user_id = fields.Many2one('res.users', string='User',
                              ondelete='set null', index=True)
    ip_address = fields.Char(string='IP Address', index=True)
    description = fields.Text(string='Description')
    details = fields.Text(string='Details (JSON)')
    resolved = fields.Boolean(string='Resolved', default=False, index=True)
    resolved_at = fields.Datetime(string='Resolved At')
    resolved_by = fields.Many2one('res.users', string='Resolved By', ondelete='set null')

    def action_resolve(self):
        self.write({'resolved': True, 'resolved_at': fields.Datetime.now(),
                    'resolved_by': self.env.uid})
