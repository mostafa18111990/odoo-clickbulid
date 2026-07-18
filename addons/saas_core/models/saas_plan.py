from odoo import models, fields, api
from odoo.exceptions import ValidationError

# Annual-only billing: plans are entered as a monthly price and the customer
# is invoiced once a year for exactly 12 x monthly. No annual discount —
# there is no monthly alternative to discount against.
ANNUAL_DISCOUNT_RATE = 0.0
TIER_PRICING = {
    'community': {1: 299.0, 2: 249.0, 3: 199.0},
    'enterprise': {1: 399.0, 2: 349.0, 3: 299.0},
}
TIER_PLAN_CODES = {
    'community': {1: 'starter', 2: 'business', 3: 'enterprise'},
    'enterprise': {1: 'starter_ee', 2: 'business_ee', 3: 'enterprise_ee'},
}


class SaasPlan(models.Model):
    _name = 'saas.plan'
    _inherit = ['saas.plan', 'saas.mixin']
    _description = 'SaaS Subscription Plan (Extended)'

    # ─── Edition selector ───────────────────────────────────────────────────
    # Determines which Odoo image hosts new tenants on this plan:
    #   community  → odoo_saas_app container (LGPL, no extra license cost)
    #   enterprise → odoo_saas_ent container (Studio, Helpdesk Pro, Subscriptions,
    #                Field Service, Documents, Sign, MRP Plan, etc.)
    edition = fields.Selection(
        selection=[('community', 'Community'), ('enterprise', 'Enterprise')],
        string='Odoo Edition', default='community', required=True, index=True,
        help='Community runs the free LGPL Odoo. Enterprise unlocks Studio, '
             'Helpdesk, Subscriptions, Field Service, Documents, Sign and more.')
    enterprise_license_cost_per_user = fields.Monetary(
        string='Odoo SA License Cost / User / Month', currency_field='currency_id',
        default=0.0,
        help='Wholesale cost Odoo SA charges per user for Enterprise. Used in '
             'monthly partner reconciliation reports.')
    enterprise_modules = fields.Text(
        string='Enterprise Modules to Auto-install',
        help='Comma-separated module names installed at provisioning time for '
             'Enterprise plans (e.g. studio,helpdesk,subscriptions).')
    currency_id = fields.Many2one('res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)

    # ─── Per-user (seat) pricing ────────────────────────────────────────────
    # flat     → monthly_price is the plan price regardless of users
    # per_user → the customer picks a seat count at signup and pays
    #            seats × price_per_user (max_users acts as the plan ceiling)
    pricing_mode = fields.Selection(
        selection=[('flat', 'Flat monthly price'), ('per_user', 'Per user (seat) pricing')],
        string='Pricing Mode', default='flat', required=True)
    price_per_user = fields.Float(string='Price / User / Month (SAR)', digits=(10, 2), default=0.0)

    yearly_price = fields.Float(string='Yearly Price (SAR)', digits=(10, 2), default=0.0)
    yearly_price_computed = fields.Float(string='Yearly Price (Auto)', compute='_compute_yearly_price', digits=(10, 2))
    yearly_discount_pct = fields.Float(string='Yearly Discount %', compute='_compute_yearly_discount', digits=(5, 1))
    extra_user_price = fields.Float(string='Extra User Price (SAR/month)', digits=(10, 2), default=0.0)
    extra_storage_price = fields.Float(string='Extra Storage Price (SAR/GB/month)', digits=(10, 2), default=0.0)
    setup_fee = fields.Float(string='One-Time Setup Fee (SAR)', digits=(10, 2), default=0.0)
    max_companies = fields.Integer(string='Max Companies', default=1)
    is_popular = fields.Boolean(string='Popular', default=False)
    is_recommended = fields.Boolean(string='Recommended', default=False)
    feature_json = fields.Text(string='Feature Matrix (JSON)')

    @api.depends('monthly_price')
    def _compute_yearly_price(self):
        for rec in self:
            rec.yearly_price_computed = round(
                rec.monthly_price * 12 * (1 - ANNUAL_DISCOUNT_RATE), 2)

    @api.depends('monthly_price', 'yearly_price', 'yearly_price_computed')
    def _compute_yearly_discount(self):
        for rec in self:
            annual_monthly = rec.monthly_price * 12
            effective_yearly = rec.yearly_price_computed
            if annual_monthly > 0 and effective_yearly > 0:
                rec.yearly_discount_pct = round((1 - effective_yearly / annual_monthly) * 100, 1)
            else:
                rec.yearly_discount_pct = 0.0

    @api.constrains('monthly_price')
    def _check_price(self):
        for rec in self:
            if rec.monthly_price < 0:
                raise ValidationError('Monthly price cannot be negative.')

    def get_effective_yearly_price(self):
        self.ensure_one()
        # Annual-only policy: exactly twelve times the displayed monthly rate.
        # The legacy stored field is synchronized during module migration.
        return round(self.monthly_price * 12 * (1 - ANNUAL_DISCOUNT_RATE), 2)

    @api.model
    def tiered_quote(self, edition, user_count, cycle='yearly'):
        edition = edition if edition in TIER_PRICING else 'community'
        seats = max(1, min(int(user_count or 1), 500))
        tier = 1 if seats == 1 else 2 if seats == 2 else 3
        unit_price = TIER_PRICING[edition][tier]
        monthly_total = round(seats * unit_price, 2)
        annual_before_discount = round(monthly_total * 12, 2)
        discount_amount = round(annual_before_discount * ANNUAL_DISCOUNT_RATE, 2)
        annual_total = round(annual_before_discount - discount_amount, 2)
        normalized_cycle = cycle if cycle in ('monthly', 'yearly') else 'yearly'
        return {
            'edition': edition, 'users': seats, 'tier': tier,
            'unit_price': unit_price, 'monthly_total': monthly_total,
            'annual_before_discount': annual_before_discount,
            'discount_rate': ANNUAL_DISCOUNT_RATE,
            'discount_pct': round(ANNUAL_DISCOUNT_RATE * 100, 1),
            'discount_amount': discount_amount, 'annual_total': annual_total,
            'cycle': normalized_cycle,
            'total': annual_total if normalized_cycle == 'yearly' else monthly_total,
        }

    @api.model
    def tier_plan_for(self, edition, user_count):
        quote = self.tiered_quote(edition, user_count)
        code = TIER_PLAN_CODES[quote['edition']][quote['tier']]
        return self.sudo().search([('code', '=ilike', code), ('active', '=', True)], limit=1)

    def price_for_users(self, user_count, cycle='monthly'):
        """Price for the given seat count under this plan's pricing mode.

        per_user: seats × price_per_user (the annual invoice is exactly
        twelve months with no annual discount).
        flat: the classic plan price, seats ignored.
        """
        self.ensure_one()
        if self.code and self.code.lower() in {
                'starter', 'business', 'enterprise',
                'starter_ee', 'business_ee', 'enterprise_ee'}:
            return self.tiered_quote(self.edition, user_count, cycle)['total']
        if self.pricing_mode == 'per_user' and self.price_per_user > 0:
            seats = max(1, int(user_count or 1))
            monthly = round(seats * self.price_per_user, 2)
            return round(monthly * 12 * (1 - ANNUAL_DISCOUNT_RATE), 2) if cycle == 'yearly' else monthly
        return self.get_effective_yearly_price() if cycle == 'yearly' else self.monthly_price

    def calculate_bill(self, billing_cycle, extra_users=0, extra_gb=0):
        self.ensure_one()
        base = self.get_effective_yearly_price() if billing_cycle == 'yearly' else self.monthly_price
        extra_users_cost = max(0, extra_users) * self.extra_user_price
        extra_storage_cost = max(0, extra_gb) * self.extra_storage_price
        if billing_cycle == 'yearly':
            extra_users_cost *= 12 * (1 - ANNUAL_DISCOUNT_RATE)
            extra_storage_cost *= 12 * (1 - ANNUAL_DISCOUNT_RATE)
        total = base + extra_users_cost + extra_storage_cost
        return {'base': base, 'extra_users': extra_users_cost, 'extra_storage': extra_storage_cost,
                'setup_fee': self.setup_fee, 'total': total, 'currency': 'SAR', 'cycle': billing_cycle}
