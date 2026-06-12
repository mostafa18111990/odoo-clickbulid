from odoo import models, fields, api


class SaasSubscriptionAddon(models.Model):
    _name = 'saas.subscription.addon'
    _description = 'Subscription Add-on'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('app_id', 'subscription_id')
    def _compute_display_name(self):
        for rec in self:
            a = rec.app_id.name if rec.app_id else '?'
            rec.display_name = f'Add-on: {a}'

    subscription_id = fields.Many2one('saas.subscription', string='Subscription', required=True,
                                      ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', related='subscription_id.tenant_id',
                                store=True, index=True)
    app_id = fields.Many2one('saas.marketplace.app', string='App', required=True, ondelete='restrict')
    price = fields.Float(string='Price', digits=(10, 2))
    pricing_model = fields.Selection(
        selection=[('monthly', 'Monthly'), ('yearly', 'Yearly'), ('one_time', 'One-Time')],
        string='Billing')
    currency = fields.Char(string='Currency', default='SAR')
    state = fields.Selection(
        selection=[('active', 'Active'), ('cancelled', 'Cancelled')],
        string='Status', default='active', index=True)
    started_at = fields.Date(string='Started', default=fields.Date.today)
    cancelled_at = fields.Date(string='Cancelled')

    def action_cancel(self):
        self.write({'state': 'cancelled', 'cancelled_at': fields.Date.today()})

    def get_monthly_amount(self):
        self.ensure_one()
        if self.pricing_model == 'yearly':
            return round(self.price / 12, 2)
        elif self.pricing_model == 'monthly':
            return self.price
        return 0.0
