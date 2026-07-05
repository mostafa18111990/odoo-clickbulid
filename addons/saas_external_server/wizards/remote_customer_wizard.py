import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RemoteCustomerWizard(models.TransientModel):
    _name = 'saas.remote.customer.wizard'
    _description = 'New customer on an external server (one-shot)'

    # ── Server: reuse an existing one or register a new one here ─────────────
    server_mode = fields.Selection(
        [('existing', 'Use an existing server'), ('new', 'Register a new server')],
        string='Server', default='existing', required=True)
    existing_server_id = fields.Many2one('saas.external.server', string='External Server')

    new_server_name = fields.Char(string='Server Name')
    host = fields.Char(string='Host / IP')
    ssh_port = fields.Integer(string='SSH Port', default=22)
    ssh_user = fields.Char(string='SSH User', default='root')
    auth_method = fields.Selection(
        [('key', 'Private Key'), ('password', 'Password')],
        string='Auth', default='key')
    ssh_private_key = fields.Text(string='SSH Private Key')
    ssh_password = fields.Char(string='SSH Password')
    base_domain = fields.Char(string='Tenant Base Domain', default='odoo.clickbulid.com')
    auto_install = fields.Boolean(
        string='Install Odoo stack on this server first', default=False,
        help='Runs the full remote install (docker + Odoo + addons). Only '
             'needed for a bare server — takes a few minutes.')

    # ── Customer / company ──────────────────────────────────────────────────
    subdomain = fields.Char(string='Subdomain', required=True)
    customer_name = fields.Char(string='Contact Name', required=True)
    customer_email = fields.Char(string='Email', required=True)
    phone = fields.Char(string='Phone')
    company_name = fields.Char(string='Company Name', required=True)
    country = fields.Selection(
        [('SA', 'Saudi Arabia'), ('AE', 'UAE'), ('EG', 'Egypt'), ('KW', 'Kuwait'),
         ('QA', 'Qatar'), ('BH', 'Bahrain'), ('OM', 'Oman'), ('JO', 'Jordan')],
        string='Country', default='SA', required=True)
    plan_id = fields.Many2one('saas.plan', string='Plan', required=True,
                              domain="[('active', '=', True)]")
    user_count = fields.Integer(string='Users (Seats)', default=1)
    industry = fields.Selection(
        selection=lambda self: self.env['saas.tenant']._fields['industry'].selection,
        string='Industry')

    def _resolve_server(self):
        if self.server_mode == 'existing':
            if not self.existing_server_id:
                raise UserError(_('Choose an existing server or switch to "Register a new server".'))
            return self.existing_server_id
        # Register a new one from the details typed here.
        for f, label in [('new_server_name', 'Server Name'), ('host', 'Host')]:
            if not self[f]:
                raise UserError(_('Please fill the server %s.', label))
        vals = {
            'name': self.new_server_name, 'host': self.host, 'ssh_port': self.ssh_port,
            'ssh_user': self.ssh_user, 'auth_method': self.auth_method,
            'ssh_private_key': self.ssh_private_key, 'ssh_password': self.ssh_password,
            'base_domain': self.base_domain,
        }
        return self.env['saas.external.server'].create(vals)

    def action_create_customer(self):
        self.ensure_one()
        server = self._resolve_server()

        # Optionally bootstrap a bare server, then require it to be online.
        if self.auto_install:
            server.action_bootstrap_stack()
        else:
            server.action_test_connection()
        if server.state != 'online':
            raise UserError(_(
                'Server "%(name)s" is not online (%(state)s). Install the stack '
                'or press Test Connection first.\n%(err)s',
                name=server.name, state=server.state, err=server.last_error or ''))

        # Create the tenant + subscription, then provision on the server.
        from odoo.addons.saas_core.services.tenant_service import TenantService
        svc = TenantService(self.env(su=True))
        tenant = svc.create_lead(
            subdomain=(self.subdomain or '').strip().lower(),
            customer_name=self.customer_name, customer_email=(self.customer_email or '').strip().lower(),
            plan_id=self.plan_id.id, company_name=self.company_name, phone=self.phone,
            country=self.country, industry=self.industry,
            user_count=self.user_count or 0)
        tenant.external_server_id = server.id
        try:
            tenant.action_provision()
        except Exception as e:
            _logger.error('Remote provision failed for %s: %s', tenant.subdomain, e)
            raise UserError(_('Tenant record created but provisioning failed:\n%s', str(e)[:500]))

        # Open the freshly created tenant.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.tenant',
            'res_id': tenant.id,
            'view_mode': 'form',
            'target': 'current',
        }
