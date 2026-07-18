from odoo.tests.common import TransactionCase


class TestTierPricing(TransactionCase):
    def test_monthly_and_yearly_tiers(self):
        cases = {
            'community': {1: (299, 3049.80), 2: (498, 5079.60), 3: (597, 6089.40), 4: (796, 8119.20)},
            'enterprise': {1: (399, 4069.80), 2: (698, 7119.60), 3: (897, 9149.40), 4: (1196, 12199.20)},
        }
        pricing = self.env['saas.plan']
        for edition, edition_cases in cases.items():
            for users, (monthly, yearly) in edition_cases.items():
                monthly_quote = pricing.tiered_quote(edition, users, 'monthly')
                yearly_quote = pricing.tiered_quote(edition, users, 'yearly')
                self.assertEqual(monthly_quote['monthly_total'], monthly)
                self.assertEqual(monthly_quote['total'], monthly)
                self.assertEqual(yearly_quote['total'], yearly)
                self.assertEqual(yearly_quote['discount_amount'], round(monthly * 12 * 0.15, 2))

    def test_public_rate_only_starts_at_three_users(self):
        pricing = self.env['saas.plan']
        self.assertEqual(pricing.tiered_quote('community', 2)['unit_price'], 249)
        self.assertEqual(pricing.tiered_quote('community', 3)['unit_price'], 199)
        self.assertEqual(pricing.tiered_quote('enterprise', 2)['unit_price'], 349)
        self.assertEqual(pricing.tiered_quote('enterprise', 3)['unit_price'], 299)

    def test_flat_and_usage_prices_use_exact_fifteen_percent_discount(self):
        plan = self.env['saas.plan'].create({
            'name': 'Annual policy test', 'code': 'annual-policy-test',
            'monthly_price': 299.0, 'yearly_price': 2990.0,
            'extra_user_price': 10.0, 'extra_storage_price': 2.0,
        })
        self.assertEqual(plan.get_effective_yearly_price(), 3049.80)
        self.assertEqual(plan.yearly_discount_pct, 15.0)
        bill = plan.calculate_bill('yearly', extra_users=1, extra_gb=1)
        self.assertEqual(bill['base'], 3049.80)
        self.assertEqual(bill['extra_users'], 102.0)
        self.assertEqual(bill['extra_storage'], 20.4)
