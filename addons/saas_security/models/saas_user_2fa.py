from odoo import models, fields, api
import secrets


class SaasUser2fa(models.Model):
    _name = 'saas.user.2fa'
    _description = 'User Two-Factor Authentication'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True)
    enabled = fields.Boolean(string='Enabled', default=False, index=True)
    method = fields.Selection(
        selection=[('totp', 'TOTP App'), ('sms', 'SMS'), ('email', 'Email Code')],
        string='Method', default='totp', required=True)
    secret = fields.Char(string='Secret', help='Encrypted TOTP secret')
    phone_number = fields.Char(string='Phone (for SMS)')
    backup_codes = fields.Text(string='Backup Codes')
    enabled_at = fields.Datetime(string='Enabled At', readonly=True)
    last_verified_at = fields.Datetime(string='Last Verified', readonly=True)

    _sql_constraints = [('user_unique', 'UNIQUE(user_id)', 'One 2FA record per user.')]

    def action_enable(self):
        codes = [secrets.token_hex(4) for _ in range(8)]
        self.write({'enabled': True,
                    'enabled_at': fields.Datetime.now(),
                    'backup_codes': '\n'.join(codes),
                    'secret': self.secret or secrets.token_hex(20)})
        self.env['saas.security.event'].sudo().create({
            'event_type': '2fa_enabled', 'severity': 'low',
            'user_id': self.user_id.id,
            'description': f'2FA enabled via {self.method}'})

    def action_disable(self):
        self.write({'enabled': False, 'backup_codes': False})
        self.env['saas.security.event'].sudo().create({
            'event_type': '2fa_disabled', 'severity': 'medium',
            'user_id': self.user_id.id,
            'description': '2FA disabled'})
