import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SSH_TIMEOUT = 20


class SaasExternalServer(models.Model):
    _name = 'saas.external.server'
    _description = 'External Server (customer-owned) for remote tenant hosting'
    _order = 'name'

    name = fields.Char(string='Server Name', required=True)
    active = fields.Boolean(default=True)

    # ── SSH connection ──────────────────────────────────────────────────────
    host = fields.Char(string='Host / IP', required=True)
    ssh_port = fields.Integer(string='SSH Port', default=22, required=True)
    ssh_user = fields.Char(string='SSH User', default='root', required=True)
    auth_method = fields.Selection(
        [('key', 'Private Key'), ('password', 'Password')],
        string='Auth Method', default='key', required=True)
    ssh_private_key = fields.Text(
        string='SSH Private Key',
        help='PEM/OpenSSH private key used to log into the server. Stored '
             'encrypted-at-rest is recommended; visible only to SaaS admins.')
    ssh_key_passphrase = fields.Char(string='Key Passphrase')
    ssh_password = fields.Char(string='SSH Password')

    # ── Remote stack layout (must mirror the ClickBuild docker stack) ───────
    odoo_container = fields.Char(string='Odoo Container', default='odoo_saas_app', required=True)
    postgres_container = fields.Char(string='Postgres Container', default='odoo_saas_postgres', required=True)
    postgres_user = fields.Char(string='Postgres User', default='odoo', required=True)
    db_owner = fields.Char(string='DB Owner Role', default='odoo_community', required=True)
    base_domain = fields.Char(
        string='Tenant Base Domain', default='odoo.clickbulid.com',
        help='Subdomains are built as <sub>.<base_domain> on this server.')

    # ── Status ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        [('draft', 'Not Checked'), ('online', 'Online'),
         ('offline', 'Unreachable'), ('error', 'Error')],
        string='Status', default='draft', readonly=True, copy=False)
    last_check = fields.Datetime(string='Last Checked', readonly=True, copy=False)
    last_error = fields.Text(string='Last Error', readonly=True, copy=False)
    docker_info = fields.Text(string='Detected Containers', readonly=True, copy=False)

    tenant_ids = fields.One2many('saas.tenant', 'external_server_id', string='Tenants')
    tenant_count = fields.Integer(compute='_compute_tenant_count', string='Tenants')

    def _compute_tenant_count(self):
        for rec in self:
            rec.tenant_count = len(rec.tenant_ids.filtered(lambda t: t.state != 'deleted'))

    # ── SSH plumbing ────────────────────────────────────────────────────────
    def _ssh_client(self):
        """Return a connected paramiko SSHClient. Caller must close()."""
        self.ensure_one()
        try:
            import paramiko
        except ImportError:
            raise UserError(_('paramiko is not installed in this Odoo image.'))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = {'hostname': self.host, 'port': self.ssh_port,
                  'username': self.ssh_user, 'timeout': SSH_TIMEOUT,
                  'banner_timeout': SSH_TIMEOUT, 'auth_timeout': SSH_TIMEOUT}
        if self.auth_method == 'key':
            if not self.ssh_private_key:
                raise UserError(_('No SSH private key set for %s.', self.name))
            pkey = self._load_key(self.ssh_private_key, self.ssh_key_passphrase)
            kwargs['pkey'] = pkey
            kwargs['look_for_keys'] = False
            kwargs['allow_agent'] = False
        else:
            if not self.ssh_password:
                raise UserError(_('No SSH password set for %s.', self.name))
            kwargs['password'] = self.ssh_password
            kwargs['look_for_keys'] = False
            kwargs['allow_agent'] = False
        client.connect(**kwargs)
        return client

    @staticmethod
    def _load_key(key_text, passphrase=None):
        import paramiko
        buf = io.StringIO(key_text.strip() + '\n')
        # Try the common key types in turn (paramiko needs the right class).
        # Build the list with getattr — paramiko 5 dropped DSSKey, and
        # referencing a missing attribute would raise before any parse.
        classes = [getattr(paramiko, n, None) for n in
                   ('Ed25519Key', 'RSAKey', 'ECDSAKey', 'DSSKey')]
        for cls in [c for c in classes if c is not None]:
            try:
                buf.seek(0)
                return cls.from_private_key(buf, password=passphrase or None)
            except Exception:
                continue
        raise UserError(_('Could not parse the SSH private key (unsupported format).'))

    def run_ssh(self, command, raise_on_error=True):
        """Run a command on the server, return (exit_code, stdout, stderr)."""
        self.ensure_one()
        client = self._ssh_client()
        try:
            _stdin, stdout, stderr = client.exec_command(command, timeout=600)
            out = stdout.read().decode('utf-8', 'replace')
            err = stderr.read().decode('utf-8', 'replace')
            code = stdout.channel.recv_exit_status()
        finally:
            client.close()
        if code != 0 and raise_on_error:
            raise UserError(_('Remote command failed (exit %(code)s):\n%(err)s',
                              code=code, err=(err or out)[:2000]))
        return code, out, err

    # ── Actions ─────────────────────────────────────────────────────────────
    def action_test_connection(self):
        self.ensure_one()
        try:
            code, out, err = self.run_ssh(
                'docker ps --format "{{.Names}}" 2>/dev/null || echo NO_DOCKER',
                raise_on_error=False)
            names = [n for n in out.split() if n]
            has_odoo = self.odoo_container in names
            has_pg = self.postgres_container in names
            if 'NO_DOCKER' in out or not names:
                self.write({'state': 'error', 'last_check': fields.Datetime.now(),
                            'last_error': 'Connected, but docker not reachable as this user.',
                            'docker_info': out[:1000]})
                msg, typ = _('Connected, but docker is not reachable.'), 'warning'
            elif not (has_odoo and has_pg):
                self.write({'state': 'error', 'last_check': fields.Datetime.now(),
                            'last_error': 'Missing containers: '
                                          f'odoo={"ok" if has_odoo else "MISSING"}, '
                                          f'postgres={"ok" if has_pg else "MISSING"}',
                            'docker_info': ', '.join(names)[:1000]})
                msg, typ = _('Connected, but required containers are missing.'), 'warning'
            else:
                self.write({'state': 'online', 'last_check': fields.Datetime.now(),
                            'last_error': False, 'docker_info': ', '.join(names)[:1000]})
                msg, typ = _('✅ Online — Odoo and Postgres containers found.'), 'success'
        except Exception as e:
            self.write({'state': 'offline', 'last_check': fields.Datetime.now(),
                        'last_error': str(e)[:2000]})
            msg, typ = _('❌ Connection failed: %s', str(e)[:200]), 'danger'
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': typ, 'message': msg, 'sticky': typ != 'success'}}
