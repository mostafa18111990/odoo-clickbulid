from odoo.tests.common import TransactionCase


class TestTenantMetrics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = cls.env['saas.plan'].search([('active', '=', True)], limit=1)
        cls.tenant = cls.env['saas.tenant'].create({
            'name': 'Metrics QA',
            'customer_name': 'Metrics QA',
            'customer_email': 'metrics-qa@example.invalid',
            'company_name': 'Metrics QA',
            'subdomain': 'metrics-qa',
            'plan_id': cls.plan.id,
            'state': 'trial',
            'api_instance_id': 'metrics_qa_db',
            'user_count': 4,
        })

    def test_database_identifier_uses_api_instance_id(self):
        self.assertEqual(self.tenant._metrics_database_name(), 'metrics_qa_db')
        self.tenant.api_instance_id = 'pending:unsafe'
        self.assertFalse(self.tenant._metrics_database_name())

    def test_purchased_seats_drive_portal_limit(self):
        self.assertEqual(self.tenant.effective_max_users(), 4)

    def test_host_metrics_status_is_not_downgraded_by_odoo_cron(self):
        self.tenant.write({
            'metrics_sync_status': 'ok',
            'backup_sync_status': 'ok',
        })
        self.assertTrue(self.tenant._host_metrics_are_current())
        self.tenant.backup_sync_status = 'missing'
        self.assertFalse(self.tenant._host_metrics_are_current())
