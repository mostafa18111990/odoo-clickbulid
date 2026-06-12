from odoo import models, fields


class SaasCouponRedemption(models.Model):
    _name = 'saas.coupon.redemption'
    _description = 'Coupon Redemption'
    _order = 'create_date desc'

    coupon_id = fields.Many2one('saas.coupon', string='Coupon', required=True,
                                ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant',
                                ondelete='set null', index=True)
    subscription_id = fields.Many2one('saas.subscription', string='Subscription',
                                      ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null')
    amount_discounted = fields.Float(string='Amount Discounted')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    redeemed_at = fields.Datetime(string='Redeemed At', default=fields.Datetime.now)
