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
