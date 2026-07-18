from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaasServerCredentialsWizard(models.TransientModel):
    _name = 'saas.server.credentials.wizard'
    _description = 'Securely update external server credentials'

    server_id = fields.Many2one('saas.external.server', required=True, readonly=True)
    auth_method = fields.Selection(
        [('key', 'Private Key'), ('password', 'Password')], required=True, default='key')
    ssh_private_key = fields.Text(
        string='SSH Private Key', compute='_compute_secret_inputs',
        inverse='_inverse_secret_inputs', store=False)
    ssh_key_passphrase = fields.Char(
        string='Key Passphrase', compute='_compute_secret_inputs',
        inverse='_inverse_secret_inputs', store=False)
    ssh_password = fields.Char(
        string='SSH Password', compute='_compute_secret_inputs',
        inverse='_inverse_secret_inputs', store=False)
    private_key_encrypted = fields.Text(copy=False)
    passphrase_encrypted = fields.Text(copy=False)
    password_encrypted = fields.Text(copy=False)

    def _compute_secret_inputs(self):
        for wizard in self:
            wizard.ssh_private_key = False
            wizard.ssh_key_passphrase = False
            wizard.ssh_password = False

    def _inverse_secret_inputs(self):
        # Values are encrypted by create/write before ORM persistence. This
        # inverse only makes the computed input fields writable in the form.
        return

    @api.model_create_multi
    def create(self, vals_list):
        from odoo.addons.saas_external_server.services.secret_vault import ExternalServerSecretVault
        for vals in vals_list:
            private_key = vals.pop('ssh_private_key', None)
            passphrase = vals.pop('ssh_key_passphrase', None)
            password = vals.pop('ssh_password', None)
            if private_key:
                vals['private_key_encrypted'] = ExternalServerSecretVault.encrypt(private_key)
            if passphrase:
                vals['passphrase_encrypted'] = ExternalServerSecretVault.encrypt(passphrase)
            if password:
                vals['password_encrypted'] = ExternalServerSecretVault.encrypt(password)
        return super().create(vals_list)

    def write(self, vals):
        from odoo.addons.saas_external_server.services.secret_vault import ExternalServerSecretVault
        vals = dict(vals)
        for plain, encrypted in (
            ('ssh_private_key', 'private_key_encrypted'),
            ('ssh_key_passphrase', 'passphrase_encrypted'),
            ('ssh_password', 'password_encrypted'),
        ):
            value = vals.pop(plain, None)
            if value:
                vals[encrypted] = ExternalServerSecretVault.encrypt(value)
        return super().write(vals)

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group('saas_core.group_saas_super_admin'):
            raise UserError(_('Only SaaS Super Admins may update server credentials.'))
        if self.auth_method == 'key' and not self.private_key_encrypted:
            raise UserError(_('Enter the SSH private key.'))
        if self.auth_method == 'password' and not self.password_encrypted:
            raise UserError(_('Enter the SSH password.'))
        from odoo.addons.saas_external_server.services.secret_vault import ExternalServerSecretVault
        self.server_id._set_credentials(
            auth_method=self.auth_method,
            private_key=ExternalServerSecretVault.decrypt(self.private_key_encrypted),
            passphrase=ExternalServerSecretVault.decrypt(self.passphrase_encrypted),
            password=ExternalServerSecretVault.decrypt(self.password_encrypted),
        )
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}
