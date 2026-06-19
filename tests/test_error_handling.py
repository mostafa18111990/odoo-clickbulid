import json
from odoo.tests import TransactionCase
from odoo.addons.saas_website.services.error_handler import ErrorHandler, HealthCheck, PlatformError


class TestErrorHandling(TransactionCase):
    """Test error handling and recovery system."""

    def setUp(self):
        super().setUp()
        self.env = self.env

    def test_error_codes(self):
        """Verify all error codes are properly defined."""
        for code in ['TENANT_PROVISION', 'DB_CONNECTION', 'PAYMENT_FAILED', 'EMAIL_SEND']:
            self.assertIn(code, ErrorHandler.ERROR_CODES)
            error_def = ErrorHandler.ERROR_CODES[code]
            self.assertIn('msg', error_def)
            self.assertIn('en', error_def)

    def test_error_logging(self):
        """Test error logging to database."""
        ErrorHandler.log_error(
            'TEST_ERROR',
            'Test error message',
            context={'test': True}
        )

        log = self.env['saas.error.log'].search([('code', '=', 'TEST_ERROR')], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.message, 'Test error message')
        self.assertEqual(log.severity, 'warning')

    def test_graceful_response(self):
        """Test graceful error response generation."""
        ar_msg = ErrorHandler.get_graceful_response('TENANT_PROVISION', 'ar')
        en_msg = ErrorHandler.get_graceful_response('TENANT_PROVISION', 'en')

        self.assertIsNotNone(ar_msg)
        self.assertIsNotNone(en_msg)
        self.assertNotEqual(ar_msg, en_msg)

    def test_alert_creation(self):
        """Test alert creation and acknowledgment."""
        alert = self.env['saas.alert'].create({
            'code': 'TEST_ALERT',
            'message': 'Test alert message',
            'severity': 'warning'
        })

        self.assertFalse(alert.acknowledged)

        alert.action_acknowledge()

        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.acknowledged_by, self.env.user)

    def test_error_recovery(self):
        """Test error recovery mechanism."""
        # Create a test error
        self.env['saas.error.log'].create({
            'code': 'TENANT_PROVISION',
            'message': 'Test provisioning error',
            'severity': 'critical'
        })

        # Get recent unresolved errors
        errors = self.env['saas.error.log'].search([
            ('code', '=', 'TENANT_PROVISION'),
            ('resolved', '=', False)
        ])

        self.assertEqual(len(errors), 1)

    def test_health_check_database(self):
        """Test database health check."""
        healthy, details = HealthCheck.check_database()
        self.assertTrue(healthy)
        self.assertIsNone(details)

    def test_error_cleanup(self):
        """Test cleanup of old error logs."""
        from datetime import datetime, timedelta

        # Create old error (> 90 days)
        old_date = datetime.now() - timedelta(days=91)
        old_error = self.env['saas.error.log'].create({
            'code': 'OLD_ERROR',
            'message': 'Old error',
            'severity': 'info',
            'create_date': old_date.strftime('%Y-%m-%d %H:%M:%S'),
            'resolved': True
        })

        # Create recent error
        recent_error = self.env['saas.error.log'].create({
            'code': 'RECENT_ERROR',
            'message': 'Recent error',
            'severity': 'info',
            'resolved': True
        })

        # Run cleanup
        self.env['saas.error.log'].cleanup_old_logs(days=90)

        # Verify old error deleted, recent kept
        old_still_exists = self.env['saas.error.log'].search([('id', '=', old_error.id)])
        recent_still_exists = self.env['saas.error.log'].search([('id', '=', recent_error.id)])

        self.assertFalse(old_still_exists)
        self.assertTrue(recent_still_exists)

    def test_alert_cleanup(self):
        """Test cleanup of old alerts."""
        from datetime import datetime, timedelta

        old_date = datetime.now() - timedelta(days=31)
        old_alert = self.env['saas.alert'].create({
            'code': 'OLD_ALERT',
            'message': 'Old alert',
            'severity': 'info',
            'create_date': old_date.strftime('%Y-%m-%d %H:%M:%S'),
            'acknowledged': True
        })

        recent_alert = self.env['saas.alert'].create({
            'code': 'RECENT_ALERT',
            'message': 'Recent alert',
            'severity': 'info',
            'acknowledged': True
        })

        self.env['saas.alert'].cleanup_old_alerts(days=30)

        old_still_exists = self.env['saas.alert'].search([('id', '=', old_alert.id)])
        recent_still_exists = self.env['saas.alert'].search([('id', '=', recent_alert.id)])

        self.assertFalse(old_still_exists)
        self.assertTrue(recent_still_exists)
