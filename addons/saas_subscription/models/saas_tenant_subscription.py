from odoo import models, fields, api, _


class SaasTenantSubscription(models.Model):
    _name = 'saas.tenant'
    _inherit = 'saas.tenant'

    current_subscription_id = fields.Many2one('saas.subscription', string='Current Subscription',
                                              ondelete='set null', index=True, copy=False)
    subscription_ids = fields.One2many('saas.subscription', 'tenant_id', string='All Subscriptions')
    subscription_count = fields.Integer(string='Subscriptions', compute='_compute_subscription_count')

    sub_status = fields.Selection(
        selection=[('trial', 'Trial'), ('active', 'Active'), ('past_due', 'Past Due'),
                   ('paused', 'Paused'), ('cancelled', 'Cancelled'), ('expired', 'Expired')],
        string='Subscription Status', related='current_subscription_id.status', store=True, index=True)
    sub_next_renewal = fields.Date(string='Next Renewal', related='current_subscription_id.next_renewal_date', store=True)
    sub_total_amount = fields.Float(string='Monthly Charge', related='current_subscription_id.total_amount',
                                    store=True, digits=(10, 2))
    sub_credit_balance = fields.Float(string='Credit Balance', related='current_subscription_id.credit_balance',
                                      store=True, digits=(10, 2))
    sub_days_to_renewal = fields.Integer(string='Days to Renewal', related='current_subscription_id.days_to_renewal')

    @api.depends('subscription_ids')
    def _compute_subscription_count(self):
        for rec in self:
            rec.subscription_count = len(rec.subscription_ids)

    def action_view_subscriptions(self):
        self.ensure_one()
        return {'name': _('Subscriptions'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.subscription', 'view_mode': 'list,form',
                'domain': [('tenant_id', '=', self.id)]}
