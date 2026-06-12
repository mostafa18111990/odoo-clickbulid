from odoo import models, fields, api
from odoo.exceptions import UserError


class SaasPaymentMethod(models.Model):
    _name = 'saas.payment.method'
    _description = 'Saved Payment Method'
    _order = 'is_default desc, create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('card_brand', 'card_last4', 'method_type')
    def _compute_display_name(self):
        for rec in self:
            if rec.card_last4:
                rec.display_name = f'{rec.card_brand or "Card"} ****{rec.card_last4}'
            else:
                rec.display_name = rec.method_type or 'Payment Method'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    gateway_id = fields.Many2one('saas.payment.gateway', string='Gateway', required=True, ondelete='restrict')
    method_type = fields.Selection(
        selection=[('card', 'Credit/Debit Card'), ('apple_pay', 'Apple Pay'), ('google_pay', 'Google Pay'),
                   ('knet', 'KNET'), ('mada', 'mada'), ('wallet', 'Mobile Wallet'), ('bank_transfer', 'Bank Transfer')],
        string='Type', default='card')
    card_brand = fields.Char(string='Card Brand')
    card_last4 = fields.Char(string='Last 4 Digits')
    card_expiry = fields.Char(string='Expiry (MM/YY)')
    card_holder = fields.Char(string='Card Holder Name')
    gateway_token = fields.Char(string='Gateway Token', groups='saas_core.group_saas_super_admin')
    gateway_customer_id = fields.Char(string='Gateway Customer ID', groups='saas_core.group_saas_super_admin')
    is_default = fields.Boolean(string='Default Method', default=False, index=True)
    is_active = fields.Boolean(string='Active', default=True, index=True)
    verified = fields.Boolean(string='Verified', default=False)

    @api.constrains('is_default')
    def _check_single_default(self):
        for rec in self.filtered('is_default'):
            others = self.search([('tenant_id', '=', rec.tenant_id.id), ('is_default', '=', True),
                                  ('id', '!=', rec.id)])
            if others:
                others.is_default = False

    def action_set_default(self):
        self.ensure_one()
        self.search([('tenant_id', '=', self.tenant_id.id), ('id', '!=', self.id)]).write({'is_default': False})
        self.is_default = True

    def action_deactivate(self):
        self.ensure_one()
        if self.is_default:
            raise UserError('Cannot deactivate the default payment method.')
        self.is_active = False
