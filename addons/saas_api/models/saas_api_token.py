from odoo import models, fields, api
import hashlib
import secrets


class SaasApiToken(models.Model):
    _name = 'saas.api.token'
    _description = 'SaaS API Token'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant',
                                ondelete='cascade', index=True)
    token_prefix = fields.Char(string='Token Prefix', readonly=True, index=True)
    token_hash = fields.Char(string='Token Hash', readonly=True, index=True)
    plain_token_once = fields.Char(string='Token (one-time view)', readonly=True,
                                   help='Only shown right after generation')
    scopes = fields.Char(string='Scopes', default='read',
                         help='Comma-separated, e.g. read,write,admin')
    rate_limit_per_minute = fields.Integer(string='Rate Limit / minute', default=60)
    last_used_at = fields.Datetime(string='Last Used', readonly=True)
    last_used_ip = fields.Char(string='Last Used IP', readonly=True)
    request_count = fields.Integer(string='Total Requests', readonly=True, default=0)
    expires_at = fields.Datetime(string='Expires At')
    revoked = fields.Boolean(string='Revoked', default=False, index=True)
    revoked_at = fields.Datetime(string='Revoked At', readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [('hash_unique', 'UNIQUE(token_hash)',
                         'Token hash collision (unexpected).')]

    @api.model_create_multi
    def create(self, vals_list):
        out = []
        for vals in vals_list:
            plain = secrets.token_urlsafe(32)
            vals['token_prefix'] = plain[:8]
            vals['token_hash'] = hashlib.sha256(plain.encode()).hexdigest()
            vals['plain_token_once'] = 'sk_' + plain
            out.append(vals)
        return super().create(out)

    def action_revoke(self):
        self.write({'revoked': True, 'revoked_at': fields.Datetime.now(), 'active': False})

    def has_scope(self, scope):
        self.ensure_one()
        scopes = (self.scopes or '').split(',')
        return scope in [s.strip() for s in scopes] or 'admin' in scopes

    @api.model
    def cron_expire_tokens(self):
        now = fields.Datetime.now()
        expired = self.search([('expires_at', '<', now), ('revoked', '=', False)])
        expired.action_revoke()
