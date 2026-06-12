from odoo import models, fields, api
import secrets


class SaasReferral(models.Model):
    _name = 'saas.referral'
    _description = 'Customer Referral'
    _order = 'create_date desc'

    name = fields.Char(string='Code', readonly=True, default='New', index=True)
    referrer_user_id = fields.Many2one('res.users', string='Referrer',
                                       required=True, ondelete='cascade', index=True)
    referrer_tenant_id = fields.Many2one('saas.tenant', string='Referrer Tenant',
                                         ondelete='set null')
    referred_email = fields.Char(string='Referred Email')
    referred_tenant_id = fields.Many2one('saas.tenant', string='Referred Tenant',
                                         ondelete='set null', index=True)
    state = fields.Selection(
        selection=[('pending', 'Pending'), ('signed_up', 'Signed Up'),
                   ('qualified', 'Qualified'), ('rewarded', 'Rewarded'),
                   ('expired', 'Expired'), ('cancelled', 'Cancelled')],
        string='State', default='pending', required=True, index=True)
    reward_amount = fields.Float(string='Reward Amount')
    rewarded_at = fields.Datetime(string='Rewarded At')
    expires_at = fields.Datetime(string='Expires At')
    notes = fields.Text(string='Notes')

    _sql_constraints = [('code_unique', 'UNIQUE(name)', 'Referral code must be unique.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = 'REF-' + secrets.token_hex(4).upper()
        return super().create(vals_list)

    def action_mark_signed_up(self, tenant):
        self.write({'state': 'signed_up', 'referred_tenant_id': tenant.id})

    def action_qualify(self):
        self.write({'state': 'qualified'})

    def action_mark_rewarded(self, amount):
        self.write({'state': 'rewarded', 'reward_amount': amount,
                    'rewarded_at': fields.Datetime.now()})
