from odoo.tests.common import TransactionCase

from ..services.provisioning_bridge import ProvisioningBridgeService


class TestSectorProvisioning(TransactionCase):
    def _tenant(self, sector, edition='community'):
        plan = self.env['saas.plan'].create({
            'name': 'Sector test %s' % sector,
            'code': 'sector-test-%s-%s' % (sector, edition),
            'allowed_modules': 'base,web,account',
            'edition': edition,
            'enterprise_modules': 'web_studio' if edition == 'enterprise' else False,
        })
        return self.env['saas.tenant'].create({
            'name': 'Sector tenant',
            'customer_name': 'Test Owner',
            'customer_email': 'sector-%s@example.com' % sector,
            'company_name': 'Sector Company',
            'subdomain': 'sector-%s-%s' % (sector, edition),
            'plan_id': plan.id,
            'edition': edition,
            'business_sector': sector,
        })

    def test_restaurant_modules_are_added_to_plan_modules(self):
        payload = ProvisioningBridgeService(self.env)._build_provision_payload(
            self._tenant('restaurant'))
        self.assertIn('base', payload['modules'])
        self.assertIn('point_of_sale', payload['modules'])
        self.assertIn('pos_restaurant', payload['modules'])
        self.assertEqual(payload['business_sector'], 'restaurant')

    def test_manufacturing_enterprise_gets_quality(self):
        payload = ProvisioningBridgeService(self.env)._build_provision_payload(
            self._tenant('manufacturing', 'enterprise'))
        self.assertIn('mrp', payload['modules'])
        self.assertIn('quality', payload['modules'])
