from odoo import _
from odoo.exceptions import UserError


class CouponService:
    def __init__(self, env):
        self.env = env

    def validate(self, code, tenant=None, plan=None, amount=0.0):
        coupon = self.env['saas.coupon'].sudo().search([('code', '=', code)], limit=1)
        if not coupon:
            return False, 'Coupon not found', None
        ok, msg = coupon.is_valid(tenant=tenant, plan=plan, amount=amount)
        return ok, msg, coupon

    def calculate_discount(self, coupon, amount):
        if coupon.discount_type == 'percent':
            return amount * (coupon.discount_value / 100.0)
        if coupon.discount_type == 'fixed':
            return min(amount, coupon.discount_value)
        return 0.0

    def redeem(self, coupon, tenant=None, subscription=None, amount_discounted=0.0):
        ok, msg = coupon.is_valid(tenant=tenant,
                                  plan=subscription.plan_id if subscription else None,
                                  amount=amount_discounted)
        if not ok:
            raise UserError(_(msg))
        red = self.env['saas.coupon.redemption'].sudo().create({
            'coupon_id': coupon.id,
            'tenant_id': tenant.id if tenant else False,
            'subscription_id': subscription.id if subscription else False,
            'user_id': self.env.uid,
            'amount_discounted': amount_discounted,
        })
        coupon.sudo().redemption_count += 1
        return red
