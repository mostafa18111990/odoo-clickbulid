import os
import tempfile
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

BRIDGE = 'odoo.addons.saas_core.services.provisioning_bridge'


class TestTenantUnlinkDestroys(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['saas.config']._get_config().use_api_bridge = False
        self.req_dir = tempfile.mkdtemp()
        patcher = mock.patch(BRIDGE + '.PROVISION_REQUEST_DIR', self.req_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _tenant(self, sub, state='active'):
        tenant = self.env['saas.tenant'].create({
            'name': 'Unlink %s' % sub,
            'customer_name': 'Owner',
            'customer_email': '%s@example.com' % sub,
            'company_name': 'Co %s' % sub,
            'subdomain': sub,
        })
        if state != tenant.state:
            tenant.with_context(bypass_fsm=True).write({'state': state})
        return tenant

    def _req(self, sub):
        return os.path.join(self.req_dir, '%s.delete.req' % sub)

    def test_unlink_queues_destruction(self):
        tenant = self._tenant('unlink-live')
        tenant.unlink()
        self.assertTrue(os.path.exists(self._req('unlink-live')))

    def test_unlink_deleted_record_still_destroys_orphan_database(self):
        tenant = self._tenant('unlink-gone', state='deleted')
        tenant.unlink()
        self.assertTrue(os.path.exists(self._req('unlink-gone')))

    def test_unlink_refused_when_destruction_cannot_be_queued(self):
        tenant = self._tenant('unlink-fail')
        with mock.patch(BRIDGE + '.PROVISION_REQUEST_DIR', self.req_dir + '-missing'):
            with self.assertRaises(UserError):
                tenant.unlink()
        self.assertTrue(tenant.exists())
