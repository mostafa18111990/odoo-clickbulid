from odoo.tests.common import TransactionCase

from ..models.sector_catalog import (
    BUSINESS_SECTORS,
    get_business_sector_options,
    get_sector_modules,
    is_valid_business_sector,
)


class TestSectorCatalog(TransactionCase):
    def test_all_public_options_map_to_catalog_entries(self):
        options = get_business_sector_options()
        self.assertEqual([option['code'] for option in options], list(BUSINESS_SECTORS))
        self.assertTrue(all(option['label_ar'] for option in options))
        self.assertTrue(all(option['label_en'] for option in options))

    def test_restaurant_gets_restaurant_pos_apps(self):
        modules = get_sector_modules('restaurant', 'community')
        self.assertIn('point_of_sale', modules)
        self.assertIn('pos_restaurant', modules)

    def test_manufacturing_enterprise_adds_quality(self):
        community = get_sector_modules('manufacturing', 'community')
        enterprise = get_sector_modules('manufacturing', 'enterprise')
        self.assertIn('mrp', community)
        self.assertNotIn('quality', community)
        self.assertIn('quality', enterprise)

    def test_services_enterprise_adds_enterprise_only_apps(self):
        community = get_sector_modules('services', 'community')
        enterprise = get_sector_modules('services', 'enterprise')
        self.assertNotIn('helpdesk', community)
        self.assertNotIn('planning', community)
        self.assertIn('helpdesk', enterprise)
        self.assertIn('planning', enterprise)

    def test_sector_validation_rejects_unknown_values(self):
        self.assertTrue(is_valid_business_sector('retail'))
        self.assertFalse(is_valid_business_sector('not-a-sector'))
        with self.assertRaises(ValueError):
            get_sector_modules('not-a-sector')
