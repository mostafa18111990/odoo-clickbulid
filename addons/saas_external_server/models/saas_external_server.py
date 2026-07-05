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
    nginx_container = fields.Char(string='Nginx Container', default='odoo_saas_nginx', required=True)
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

    def _sftp_put_bytes(self, client, data, remote_path):
        """Upload in-memory bytes to remote_path over the given SSH client.

        Uses putfo (chunked, with a size check) — a single write() of a large
        buffer can silently truncate over SFTP.
        """
        import io as _io
        sftp = client.open_sftp()
        try:
            attr = sftp.putfo(_io.BytesIO(data), remote_path, confirm=True)
            if attr.st_size != len(data):
                raise UserError(_('Upload truncated: %(got)s of %(exp)s bytes',
                                  got=attr.st_size, exp=len(data)))
        finally:
            sftp.close()

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

    # ── One-click remote bootstrap ──────────────────────────────────────────
    # Cybrosys modules every remote host needs (kept small — the full repo is
    # 3.4 GB; we ship only what tenants actually install).
    _ESSENTIAL_CYBROSYS = [
        'base_accounting_kit', 'base_account_budget', 'account_day_book',
        'base_hospital_management', 'dental_clinical_management', 'medical_lab_management',
    ]
    _PLATFORM_ADDONS = '/mnt/extra-addons'
    _CYBROSYS_SRC = '/mnt/cybrosys/CybroAddons'
    ROOT = '/opt/odoo-saas'

    def _bootstrap_infra_cmd(self):
        """The idempotent shell that turns a bare VPS into a valid host."""
        r = self.ROOT
        return f'''set -e
command -v docker >/dev/null 2>&1 || (curl -fsSL https://get.docker.com | sh)
systemctl enable --now docker 2>/dev/null || true
mkdir -p {r}/config {r}/addons {r}/nginx-tenants {r}/cert-requests {r}/certbot/www /opt/backups/deleted
[ -f {r}/.pg_password ] || (openssl rand -hex 24 > {r}/.pg_password && chmod 600 {r}/.pg_password)
PGPASS=$(cat {r}/.pg_password)
if [ ! -f {r}/config/odoo.conf ]; then cat > {r}/config/odoo.conf <<CONF
[options]
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
data_dir = /var/lib/odoo
db_host = {self.postgres_container}
db_port = 5432
db_user = {self.db_owner}
db_password = $PGPASS
dbfilter = ^%d$
list_db = False
proxy_mode = True
workers = 2
CONF
fi
if [ ! -f {r}/docker-compose.yml ]; then cat > {r}/docker-compose.yml <<COMPOSE
services:
  {self.postgres_container}:
    image: postgres:15-alpine
    container_name: {self.postgres_container}
    environment: {{ POSTGRES_USER: {self.postgres_user}, POSTGRES_PASSWORD: "$PGPASS", POSTGRES_DB: postgres }}
    volumes: [ "./pgdata:/var/lib/postgresql/data" ]
    restart: unless-stopped
  {self.odoo_container}:
    image: clickbuild/odoo-community:19
    container_name: {self.odoo_container}
    depends_on: [ {self.postgres_container} ]
    volumes: [ "./config:/etc/odoo", "./addons:/mnt/extra-addons", "odoo-data:/var/lib/odoo" ]
    restart: unless-stopped
  {self.nginx_container}:
    image: nginx:alpine
    container_name: {self.nginx_container}
    ports: [ "80:80", "443:443" ]
    volumes: [ "./nginx-tenants:/etc/nginx/conf.d:ro", "./certbot/www:/var/www/certbot:ro", "/etc/letsencrypt:/etc/letsencrypt:ro" ]
    restart: unless-stopped
volumes: {{ odoo-data: {{}} }}
COMPOSE
fi
cd {r} && docker compose up -d
sleep 8
docker exec {self.postgres_container} psql -U {self.postgres_user} -tAc "select 1 from pg_roles where rolname='{self.db_owner}'" | grep -qx 1 || docker exec {self.postgres_container} psql -U {self.postgres_user} -c "CREATE ROLE {self.db_owner} LOGIN PASSWORD '$PGPASS' CREATEDB;"
docker exec -u root {self.odoo_container} pip3 install --break-system-packages -q python-barcode paramiko 2>/dev/null || true
echo BOOTSTRAP_INFRA_OK'''

    def action_bootstrap_stack(self):
        """One click: install docker + the full Odoo stack + platform addons
        on a bare server over SSH, then verify. Idempotent — safe to re-run."""
        self.ensure_one()
        import tarfile, io as _io, os as _os
        try:
            client = self._ssh_client()
        except Exception as e:
            self.write({'state': 'offline', 'last_error': str(e)[:2000],
                        'last_check': fields.Datetime.now()})
            return self._notify('danger', _('SSH failed: %s', str(e)[:200]))
        try:
            # 1. Infra (docker, dirs, conf, compose, role, deps).
            _in, out, err = client.exec_command(self._bootstrap_infra_cmd(), timeout=900)
            infra_log = out.read().decode('utf-8', 'replace') + err.read().decode('utf-8', 'replace')
            if 'BOOTSTRAP_INFRA_OK' not in infra_log:
                raise UserError(_('Infra step failed:\n%s', infra_log[-1500:]))

            # 2. Ship platform addons + the essential Cybrosys modules as one
            #    tar built here (the SaaS container can read both mounts).
            buf = _io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                if _os.path.isdir(self._PLATFORM_ADDONS):
                    for name in _os.listdir(self._PLATFORM_ADDONS):
                        tar.add(_os.path.join(self._PLATFORM_ADDONS, name), arcname=name)
                for mod in self._ESSENTIAL_CYBROSYS:
                    src = _os.path.join(self._CYBROSYS_SRC, mod)
                    if _os.path.isdir(src):
                        tar.add(src, arcname=mod)
            self._sftp_put_bytes(client, buf.getvalue(), '/tmp/saas_addons.tgz')
            _in, out, err = client.exec_command(
                f'tar -xzf /tmp/saas_addons.tgz -C {self.ROOT}/addons && '
                f'rm -f /tmp/saas_addons.tgz && '
                f'docker exec {self.odoo_container} odoo --config=/etc/odoo/odoo.conf '
                f'-d postgres --stop-after-init --no-http 2>/dev/null; echo ADDONS_OK', timeout=300)
            addons_log = out.read().decode('utf-8', 'replace')
        finally:
            client.close()

        # 3. Re-check to flip status to online.
        self.action_test_connection()
        if self.state == 'online':
            return self._notify('success', _('✅ Stack installed and server is online. '
                                             'You can now provision tenants here.'))
        return self._notify('warning', _('Stack installed but the health check did not pass — '
                                         'open the server and press Test Connection.'))

    def _notify(self, typ, msg):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': typ, 'message': msg, 'sticky': typ != 'success'}}

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
