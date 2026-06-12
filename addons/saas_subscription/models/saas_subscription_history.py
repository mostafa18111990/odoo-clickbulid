from odoo import models, fields, api
from odoo.exceptions import UserError

HISTORY_EVENTS = [
    ('created', 'Subscription Created'), ('trial_started', 'Trial Started'),
    ('trial_expired', 'Trial Expired'), ('converted', 'Trial -> Paid'),
    ('renewed', 'Renewed'), ('upgraded', 'Plan Upgraded'), ('downgraded', 'Plan Downgraded'),
    ('cycle_changed', 'Billing Cycle Changed'), ('paused', 'Paused'), ('resumed', 'Resumed'),
    ('cancelled', 'Cancelled'), ('credit_applied', 'Credit Applied'),
    ('coupon_applied', 'Coupon Applied'), ('payment_success', 'Payment Success'),
    ('payment_failed', 'Payment Failed'), ('amount_adjusted', 'Amount Adjusted'),
    ('usage_recorded', 'Usage Recorded'),
]


class SaasSubscriptionHistory(models.Model):
    _name = 'saas.subscription.history'
    _description = 'Subscription History'
    _order = 'create_date desc'
    _rec_name = 'event_type'

    subscription_id = fields.Many2one('saas.subscription', string='Subscription', required=True,
                                      ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', related='subscription_id.tenant_id',
                                store=True, index=True)
    event_type = fields.Selection(selection=HISTORY_EVENTS, string='Event', required=True, index=True)
    old_plan_id = fields.Many2one('saas.plan', string='From Plan')
    new_plan_id = fields.Many2one('saas.plan', string='To Plan')
    old_cycle = fields.Selection([('monthly', 'Monthly'), ('yearly', 'Yearly')], string='From Cycle')
    new_cycle = fields.Selection([('monthly', 'Monthly'), ('yearly', 'Yearly')], string='To Cycle')
    amount = fields.Float(string='Amount', digits=(10, 2))
    proration_amount = fields.Float(string='Proration', digits=(10, 2))
    credit_amount = fields.Float(string='Credit Given', digits=(10, 2))
    currency = fields.Char(string='Currency', default='SAR')
    coupon_code = fields.Char(string='Coupon Code')
    discount_pct = fields.Float(string='Discount %', digits=(5, 2))
    period_start = fields.Date(string='Period Start')
    period_end = fields.Date(string='Period End')
    description = fields.Text(string='Description')
    user_id = fields.Many2one('res.users', string='Performed By', default=lambda self: self.env.uid)

    def write(self, vals):
        raise UserError('Subscription history is immutable.')

    def unlink(self):
        raise UserError('Subscription history cannot be deleted.')

    @api.model
    def record(self, subscription, event_type, **kwargs):
        vals = {'subscription_id': subscription.id, 'event_type': event_type}
        vals.update(kwargs)
        return self.sudo().create(vals)
