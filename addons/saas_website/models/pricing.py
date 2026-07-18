from odoo import api, models


RATES = {
    'community': {1: 299.0, 2: 249.0, 3: 199.0},
    'enterprise': {1: 399.0, 2: 349.0, 3: 299.0},
}
PLAN_CODES = {
    'community': {1: 'starter', 2: 'business', 3: 'enterprise'},
    'enterprise': {1: 'starter_ee', 2: 'business_ee', 3: 'enterprise_ee'},
}


class SaasPlanPricing(models.Model):
    _inherit = 'saas.plan'

    @api.model
    def tiered_quote(self, edition, user_count, cycle='yearly'):
        edition = edition if edition in RATES else 'community'
        seats = max(1, min(int(user_count or 1), 500))
        tier = 1 if seats == 1 else 2 if seats == 2 else 3
        unit = RATES[edition][tier]
        monthly = round(seats * unit, 2)
        before = round(monthly * 12, 2)
        saving = 0.0
        annual = before
        cycle = cycle if cycle in ('monthly', 'yearly') else 'yearly'
        return {'edition': edition, 'users': seats, 'tier': tier, 'unit_price': unit,
                'monthly_total': monthly, 'annual_before_discount': before,
                'discount_pct': 0.0, 'discount_amount': saving,
                'annual_total': annual, 'cycle': cycle,
                'total': annual if cycle == 'yearly' else monthly}

    @api.model
    def tier_plan_for(self, edition, user_count):
        quote = self.tiered_quote(edition, user_count)
        code = PLAN_CODES[quote['edition']][quote['tier']]
        return self.sudo().search([('code', '=ilike', code), ('active', '=', True)], limit=1)

    def price_for_users(self, user_count, cycle='monthly'):
        self.ensure_one()
        if self.code and self.code.lower() in {code for plans in PLAN_CODES.values() for code in plans.values()}:
            return self.tiered_quote(self.edition, user_count, cycle)['total']
        return super().price_for_users(user_count, cycle)
