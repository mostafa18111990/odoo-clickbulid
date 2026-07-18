import os

from cryptography.fernet import Fernet

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.saas_external_server.services.secret_vault import (
    ExternalServerSecretVault,
    MASTER_KEY_ENV,
)


@tagged('post_install', '-at_install')
class TestExternalServerSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.previous_key = os.environ.get(MASTER_KEY_ENV)
        os.environ[MASTER_KEY_ENV] = Fernet.generate_key().decode()
        cls.super_admin = cls.env.ref('base.user_admin')
        cls.super_admin_group = cls.env.ref('saas_core.group_saas_super_admin')
        cls.super_admin.write({'group_ids': [(4, cls.super_admin_group.id)]})

    @classmethod
    def tearDownClass(cls):
        if cls.previous_key is None:
            os.environ.pop(MASTER_KEY_ENV, None)
        else:
            os.environ[MASTER_KEY_ENV] = cls.previous_key
        super().tearDownClass()

    def _server_vals(self, **extra):
        vals = {
            'name': 'Dedicated Test Server',
            'host': '192.0.2.20',
            'base_domain': 'customer.example.com',
        }
        vals.update(extra)
        return vals

    def test_credentials_are_encrypted_and_never_stored_plaintext(self):
        server = self.env['saas.external.server'].with_user(
            self.super_admin).create(self._server_vals())
        private_key = '-----BEGIN OPENSSH PRIVATE KEY-----\ntest-only\n-----END OPENSSH PRIVATE KEY-----'
        server._set_credentials('key', private_key=private_key, passphrase='secret-passphrase')

        self.assertTrue(server.ssh_private_key_encrypted.startswith('fernet:v1:'))
        self.assertNotIn('BEGIN OPENSSH', server.ssh_private_key_encrypted)
        self.assertNotIn('secret-passphrase', server.ssh_key_passphrase_encrypted)
        self.assertEqual(
            ExternalServerSecretVault.decrypt(server.ssh_private_key_encrypted), private_key)
        self.assertEqual(
            ExternalServerSecretVault.decrypt(server.ssh_key_passphrase_encrypted),
            'secret-passphrase')

    def test_manager_cannot_register_external_server(self):
        manager_group = self.env.ref('saas_tenant_manager.group_saas_admin')
        user = self.env['res.users'].create({
            'name': 'Ordinary SaaS Admin',
            'login': 'ordinary-saas-admin-test',
            'group_ids': [(6, 0, [manager_group.id])],
        })
        with self.assertRaises(UserError):
            self.env['saas.external.server'].with_user(user).create(self._server_vals())

    def test_host_change_invalidates_pinned_fingerprint(self):
        server = self.env['saas.external.server'].with_user(
            self.super_admin).create(self._server_vals(
            ssh_host_key_fingerprint='SHA256:test', ssh_host_key_type='ssh-ed25519'))
        server.write({'host': '192.0.2.21'})
        self.assertFalse(server.ssh_host_key_fingerprint)
        self.assertEqual(server.state, 'draft')

    def test_credentials_wizard_never_persists_plaintext(self):
        server = self.env['saas.external.server'].with_user(
            self.super_admin).create(self._server_vals())
        wizard = self.env['saas.server.credentials.wizard'].with_user(
            self.super_admin).create({
                'server_id': server.id,
                'auth_method': 'password',
                'ssh_password': 'temporary-wizard-secret',
            })
        self.assertFalse(wizard.ssh_password)
        self.assertTrue(wizard.password_encrypted.startswith('fernet:v1:'))
        self.assertNotIn('temporary-wizard-secret', wizard.password_encrypted)
        self.assertEqual(
            ExternalServerSecretVault.decrypt(wizard.password_encrypted),
            'temporary-wizard-secret')

    def test_rejects_unsafe_container_name(self):
        with self.assertRaises(UserError):
            self.env['saas.external.server'].with_user(
                self.super_admin).create(self._server_vals(
                odoo_container='odoo; touch /tmp/unsafe'))
