import base64
import hashlib
import io
import logging
import re
import socket

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SSH_TIMEOUT = 20


def _host_key_fingerprint(key):
    digest = hashlib.sha256(key.asbytes()).digest()
    return 'SHA256:' + base64.b64encode(digest).decode('ascii').rstrip('=')


class _PinnedFingerprintPolicy:
    """Paramiko policy that accepts only the fingerprint pinned by an admin."""

    def __init__(self, expected):
        self.expected = expected

    def missing_host_key(self, client, hostname, key):
        import paramiko
        actual = _host_key_fingerprint(key)
        if not self.expected or actual != self.expected:
            raise paramiko.SSHException(
                f'SSH host key mismatch for {hostname}: expected '
                f'{self.expected or "<not pinned>"}, received {actual}')
        client.get_host_keys().add(hostname, key.get_name(), key)


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
    ssh_private_key_encrypted = fields.Text(
        string='Encrypted SSH Private Key', copy=False,
        groups='saas_core.group_saas_super_admin')
    ssh_key_passphrase_encrypted = fields.Char(
        string='Encrypted Key Passphrase', copy=False,
        groups='saas_core.group_saas_super_admin')
    ssh_password_encrypted = fields.Char(
        string='Encrypted SSH Password', copy=False,
        groups='saas_core.group_saas_super_admin')
    credential_status = fields.Char(
        string='Credentials', compute='_compute_credential_status')
    ssh_host_key_fingerprint = fields.Char(
        string='Pinned SSH Fingerprint', readonly=True, copy=False,
        groups='saas_core.group_saas_super_admin')
    ssh_host_key_type = fields.Char(
        string='SSH Host Key Type', readonly=True, copy=False,
        groups='saas_core.group_saas_super_admin')

    # ── Remote stack layout (must mirror the ClickBuild docker stack) ───────
    odoo_container = fields.Char(string='Odoo Container', default='odoo_saas_app', required=True)
    postgres_container = fields.Char(string='Postgres Container', default='odoo_saas_postgres', required=True)
    nginx_container = fields.Char(string='Nginx Container', default='odoo_saas_nginx', required=True)
    postgres_user = fields.Char(string='Postgres User', default='odoo', required=True)
    db_owner = fields.Char(string='DB Owner Role', default='odoo_community', required=True)
    base_domain = fields.Char(
        string='Tenant Base Domain', default='odoo.clickbulid.com',
        help='Subdomains are built as <sub>.<base_domain> on this server.')
    letsencrypt_email = fields.Char(string="Let's Encrypt Email", default='sales@clickbuild.com')

    # Administrative ownership and service controls. These fields are never
    # exposed by portal/website views and the whole model is Super Admin-only.
    server_owner = fields.Selection(
        [('customer', 'Customer-owned'), ('company', 'Company-owned')],
        string='Server Owner', default='customer', required=True)
    customer_id = fields.Many2one('res.partner', string='Customer', ondelete='restrict')
    service_start_date = fields.Date(string='Service Start')
    service_end_date = fields.Date(string='Service End')
    support_level = fields.Selection(
        [('standard', 'Standard'), ('priority', 'Priority'), ('managed', 'Fully Managed')],
        string='Support Level', default='managed', required=True)
    billing_responsibility = fields.Selection(
        [('customer', 'Customer'), ('company', 'Company')],
        string='Server & Domain Billing', default='customer', required=True)
    backup_location = fields.Char(string='Off-server Backup Location')
    backup_retention_days = fields.Integer(string='Backup Retention (days)', default=14)
    max_tenants = fields.Integer(
        string='Maximum Tenants', default=1, required=True,
        help='Keep this at 1 for a dedicated customer server.')

    # ── Status ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        [('draft', 'Not Checked'), ('online', 'Online'),
         ('offline', 'Unreachable'), ('error', 'Error')],
        string='Status', default='draft', readonly=True, copy=False)
    last_check = fields.Datetime(string='Last Checked', readonly=True, copy=False)
    last_error = fields.Text(string='Last Error', readonly=True, copy=False)
    docker_info = fields.Text(string='Detected Containers', readonly=True, copy=False)
    operating_system = fields.Char(string='Operating System', readonly=True, copy=False)
    docker_version = fields.Char(string='Docker Version', readonly=True, copy=False)
    cpu_cores = fields.Integer(string='CPU Cores', readonly=True, copy=False)
    memory_total_mb = fields.Integer(string='Memory (MB)', readonly=True, copy=False)
    disk_total_gb = fields.Float(string='Disk Total (GB)', readonly=True, copy=False)
    disk_free_gb = fields.Float(string='Disk Free (GB)', readonly=True, copy=False)
    disk_used_percent = fields.Float(string='Disk Used %', readonly=True, copy=False)
    dns_status = fields.Selection(
        [('unchecked', 'Not Checked'), ('valid', 'Valid'), ('warning', 'Needs Attention')],
        string='DNS Status', default='unchecked', readonly=True, copy=False)
    readiness_summary = fields.Text(string='Readiness Summary', readonly=True, copy=False)

    tenant_ids = fields.One2many('saas.tenant', 'external_server_id', string='Tenants')
    tenant_count = fields.Integer(compute='_compute_tenant_count', string='Tenants')
    available_slots = fields.Integer(compute='_compute_tenant_count', string='Available Slots')

    def _compute_tenant_count(self):
        for rec in self:
            rec.tenant_count = len(rec.tenant_ids.filtered(lambda t: t.state != 'deleted'))
            rec.available_slots = max((rec.max_tenants or 0) - rec.tenant_count, 0)

    def _compute_credential_status(self):
        for rec in self:
            configured = (rec.ssh_private_key_encrypted if rec.auth_method == 'key'
                          else rec.ssh_password_encrypted)
            rec.credential_status = _('Encrypted and configured') if configured else _('Not configured')

    def _check_super_admin(self):
        if not self.env.user.has_group('saas_core.group_saas_super_admin'):
            raise UserError(_('Only SaaS Super Admins may manage external servers.'))

    def _audit(self, action, description, severity='info', old_values=None, new_values=None):
        self.ensure_one()
        self.env['saas.audit.log'].log_action(
            model=self._name, record_id=self.id, action=action,
            description=description, severity=severity,
            old_values=old_values, new_values=new_values)

    def _set_credentials(self, auth_method, private_key=None, passphrase=None, password=None):
        self.ensure_one()
        self._check_super_admin()
        from odoo.addons.saas_external_server.services.secret_vault import ExternalServerSecretVault
        vals = {
            'auth_method': auth_method,
            'ssh_private_key_encrypted': False,
            'ssh_key_passphrase_encrypted': False,
            'ssh_password_encrypted': False,
        }
        if auth_method == 'key':
            vals.update({
                'ssh_private_key_encrypted': ExternalServerSecretVault.encrypt(private_key),
                'ssh_key_passphrase_encrypted': ExternalServerSecretVault.encrypt(passphrase),
            })
        else:
            vals['ssh_password_encrypted'] = ExternalServerSecretVault.encrypt(password)
        self.write(vals)
        self._audit('security', f'Credentials securely updated for external server {self.name}.')

    def action_open_credentials(self):
        self.ensure_one()
        self._check_super_admin()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.server.credentials.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_server_id': self.id, 'default_auth_method': self.auth_method},
        }

    @api.constrains('max_tenants', 'backup_retention_days')
    def _check_positive_limits(self):
        for rec in self:
            if rec.max_tenants < 1:
                raise UserError(_('Maximum tenants must be at least 1.'))
            if rec.backup_retention_days < 1:
                raise UserError(_('Backup retention must be at least 1 day.'))

    @api.constrains(
        'odoo_container', 'postgres_container', 'nginx_container',
        'postgres_user', 'db_owner', 'base_domain')
    def _check_safe_infrastructure_names(self):
        container_re = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
        db_identifier_re = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,62}$')
        domain_re = re.compile(
            r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$')
        for rec in self:
            for value in (rec.odoo_container, rec.postgres_container, rec.nginx_container):
                if not container_re.match(value or ''):
                    raise UserError(_('Invalid Docker container name: %s', value))
            for value in (rec.postgres_user, rec.db_owner):
                if not db_identifier_re.match(value or ''):
                    raise UserError(_('Invalid PostgreSQL identifier: %s', value))
            if not domain_re.match((rec.base_domain or '').strip()):
                raise UserError(_('Enter a valid tenant base domain.'))

    # ── SSH plumbing ────────────────────────────────────────────────────────
    def _ssh_client(self):
        """Return a connected paramiko SSHClient. Caller must close()."""
        self.ensure_one()
        try:
            import paramiko
        except ImportError:
            raise UserError(_('paramiko is not installed in this Odoo image.'))
        if not self.ssh_host_key_fingerprint:
            raise UserError(_(
                'The SSH host key is not pinned. Scan and verify the fingerprint first.'))
        from odoo.addons.saas_external_server.services.secret_vault import ExternalServerSecretVault
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(
            _PinnedFingerprintPolicy(self.ssh_host_key_fingerprint))
        kwargs = {'hostname': self.host, 'port': self.ssh_port,
                  'username': self.ssh_user, 'timeout': SSH_TIMEOUT,
                  'banner_timeout': SSH_TIMEOUT, 'auth_timeout': SSH_TIMEOUT}
        if self.auth_method == 'key':
            if not self.ssh_private_key_encrypted:
                raise UserError(_('No SSH private key set for %s.', self.name))
            private_key = ExternalServerSecretVault.decrypt(self.ssh_private_key_encrypted)
            passphrase = ExternalServerSecretVault.decrypt(self.ssh_key_passphrase_encrypted)
            pkey = self._load_key(private_key, passphrase)
            kwargs['pkey'] = pkey
            kwargs['look_for_keys'] = False
            kwargs['allow_agent'] = False
        else:
            if not self.ssh_password_encrypted:
                raise UserError(_('No SSH password set for %s.', self.name))
            kwargs['password'] = ExternalServerSecretVault.decrypt(self.ssh_password_encrypted)
            kwargs['look_for_keys'] = False
            kwargs['allow_agent'] = False
        client.connect(**kwargs)
        return client

    def action_scan_host_key(self):
        """Pin the first SSH fingerprint or verify an already pinned one."""
        self.ensure_one()
        self._check_super_admin()
        try:
            import paramiko
        except ImportError as exc:
            raise UserError(_('paramiko is not installed in this Odoo image.')) from exc
        transport = None
        sock = None
        try:
            sock = socket.create_connection((self.host, self.ssh_port), timeout=SSH_TIMEOUT)
            transport = paramiko.Transport(sock)
            transport.start_client(timeout=SSH_TIMEOUT)
            key = transport.get_remote_server_key()
            fingerprint = _host_key_fingerprint(key)
            key_type = key.get_name()
        except Exception as exc:
            raise UserError(_('Unable to read the SSH host key: %s', str(exc)[:300])) from exc
        finally:
            if transport:
                transport.close()
            elif sock:
                sock.close()
        if self.ssh_host_key_fingerprint and self.ssh_host_key_fingerprint != fingerprint:
            expected = self.ssh_host_key_fingerprint
            self.write({
                'state': 'error',
                'last_check': fields.Datetime.now(),
                'last_error': _(
                    'SSH host key mismatch. Expected %(expected)s, received %(actual)s.',
                    expected=expected, actual=fingerprint),
            })
            self._audit(
                'security', f'SSH host key mismatch detected for {self.name}.',
                severity='critical',
                old_values={'fingerprint': expected},
                new_values={'fingerprint': fingerprint})
            return self._notify('danger', _(
                'SECURITY WARNING: the server fingerprint changed. Expected %(expected)s, '
                'received %(actual)s. Do not continue until the server owner confirms it.',
                expected=expected, actual=fingerprint))
        first_pin = not self.ssh_host_key_fingerprint
        self.write({
            'ssh_host_key_fingerprint': fingerprint,
            'ssh_host_key_type': key_type,
            'state': 'draft' if first_pin else self.state,
        })
        self._audit(
            'security', f'SSH host key {"pinned" if first_pin else "verified"} for {self.name}.',
            severity='warning' if first_pin else 'info',
            new_values={'fingerprint': fingerprint, 'key_type': key_type})
        return self._notify(
            'warning' if first_pin else 'success',
            _('Fingerprint %(fingerprint)s was %(action)s. Verify it with the server provider.',
              fingerprint=fingerprint, action=_('pinned') if first_pin else _('verified')))

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
        self._check_super_admin()
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
            self.action_install_backup_job()
            self._audit('provision', f'Odoo stack installed or reconciled on {self.name}.')
            return self._notify('success', _('✅ Stack installed and server is online. '
                                             'You can now provision tenants here.'))
        return self._notify('warning', _('Stack installed but the health check did not pass — '
                                         'open the server and press Test Connection.'))

    def _notify(self, typ, msg):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': typ, 'message': msg, 'sticky': typ != 'success'}}

    def action_install_backup_job(self):
        """Install an idempotent daily database + filestore backup job."""
        self.ensure_one()
        self._check_super_admin()
        import shlex
        destination = (self.backup_location or '/opt/backups/daily').strip()
        if not destination.startswith('/') or any(ch in destination for ch in ('\n', '\r', '\x00')):
            raise UserError(_('Backup location must be an absolute server path.'))
        script = f'''#!/bin/sh
set -eu
DEST={shlex.quote(destination)}
STAMP=$(date -u +%Y%m%d_%H%M%S)
mkdir -p "$DEST"
for DB in $(docker exec {self.postgres_container} psql -U {self.postgres_user} -d postgres -At -c "select datname from pg_database where datallowconn and not datistemplate and datname <> 'postgres'"); do
  docker exec {self.postgres_container} pg_dump -U {self.postgres_user} -Fc "$DB" > "$DEST/${{DB}}_${{STAMP}}.dump"
  docker exec {self.odoo_container} sh -c "test -d /var/lib/odoo/filestore/$DB && tar -C /var/lib/odoo/filestore -czf - $DB || true" > "$DEST/${{DB}}_${{STAMP}}_filestore.tar.gz"
done
find "$DEST" -type f -mtime +{int(self.backup_retention_days)} -delete
'''
        payload = base64.b64encode(script.encode()).decode()
        cron = '25 2 * * * root /usr/local/sbin/clickbuild-tenant-backup >/var/log/clickbuild-tenant-backup.log 2>&1\n'
        cron_payload = base64.b64encode(cron.encode()).decode()
        self.run_ssh(
            f'echo {payload} | base64 -d > /usr/local/sbin/clickbuild-tenant-backup && '
            'chmod 700 /usr/local/sbin/clickbuild-tenant-backup && '
            f'echo {cron_payload} | base64 -d > /etc/cron.d/clickbuild-tenant-backup && '
            'chmod 644 /etc/cron.d/clickbuild-tenant-backup')
        self._audit('backup', f'Daily backup job installed on {self.name}.')
        return self._notify('success', _('Daily database and filestore backup job installed.'))

    # ── Actions ─────────────────────────────────────────────────────────────
    def action_test_connection(self):
        self.ensure_one()
        self._check_super_admin()
        try:
            code, out, err = self.run_ssh(
                "set -e; "
                "printf 'OS='; (grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '\"' || uname -s); "
                "printf 'CPU='; nproc; "
                "printf 'MEM_KB='; awk '/MemTotal/{print $2}' /proc/meminfo; "
                "printf 'DISK_KB='; df -Pk /opt | awk 'NR==2{print $2}'; "
                "printf 'DISK_FREE_KB='; df -Pk /opt | awk 'NR==2{print $4}'; "
                "printf 'DISK_USED='; df -Pk /opt | awk 'NR==2{gsub(/%/,\"\",$5);print $5}'; "
                "printf 'DOCKER='; docker --version | head -1; "
                "printf 'CONTAINERS='; docker ps --format '{{.Names}}' | paste -sd, -",
                raise_on_error=False)
            probe = {}
            for line in out.splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    probe[key.strip()] = value.strip()
            names = [n for n in probe.get('CONTAINERS', '').split(',') if n]
            has_odoo = self.odoo_container in names
            has_pg = self.postgres_container in names
            has_nginx = self.nginx_container in names
            if code != 0 or not names:
                self.write({
                    'state': 'error', 'last_check': fields.Datetime.now(),
                    'last_error': (err or 'Connected, but Docker is not reachable.')[:2000],
                    'readiness_summary': _('Docker health probe failed.'),
                })
                msg, typ = _('Connected, but Docker is not reachable.'), 'warning'
            elif not (has_odoo and has_pg and has_nginx):
                missing = [name for ok, name in (
                    (has_odoo, self.odoo_container),
                    (has_pg, self.postgres_container),
                    (has_nginx, self.nginx_container),
                ) if not ok]
                self.write({'state': 'error', 'last_check': fields.Datetime.now(),
                            'last_error': 'Missing containers: ' + ', '.join(missing),
                            'docker_info': ', '.join(names)[:1000],
                            'readiness_summary': _('Required containers are missing.')})
                msg = _('Connected, but required containers are missing: %s', ', '.join(missing))
                typ = 'warning'
            else:
                try:
                    resolved = socket.gethostbyname(self.base_domain)
                    target = socket.gethostbyname(self.host)
                    dns_ok = resolved == target
                except OSError:
                    resolved, target, dns_ok = '', '', False
                disk_used = float(probe.get('DISK_USED') or 0)
                warnings = []
                if disk_used >= 85:
                    warnings.append(_('Disk usage is %s%%.', disk_used))
                if not dns_ok:
                    warnings.append(_(
                        'DNS %(domain)s resolves to %(resolved)s, not server %(target)s.',
                        domain=self.base_domain, resolved=resolved or '?', target=target or '?'))
                self.write({
                    'state': 'online', 'last_check': fields.Datetime.now(),
                    'last_error': '\n'.join(warnings) or False,
                    'docker_info': ', '.join(names)[:1000],
                    'operating_system': probe.get('OS'),
                    'docker_version': probe.get('DOCKER'),
                    'cpu_cores': int(probe.get('CPU') or 0),
                    'memory_total_mb': int(probe.get('MEM_KB') or 0) // 1024,
                    'disk_total_gb': round(int(probe.get('DISK_KB') or 0) / 1024 / 1024, 2),
                    'disk_free_gb': round(int(probe.get('DISK_FREE_KB') or 0) / 1024 / 1024, 2),
                    'disk_used_percent': disk_used,
                    'dns_status': 'valid' if dns_ok else 'warning',
                    'readiness_summary': '\n'.join(warnings) if warnings else _('All readiness checks passed.'),
                })
                msg = _('Server is online. All required containers were found.')
                typ = 'warning' if warnings else 'success'
            self._audit(
                'security', f'External server readiness check completed for {self.name}: {self.state}.',
                severity='warning' if self.state != 'online' or self.last_error else 'info')
        except Exception as e:
            self.write({'state': 'offline', 'last_check': fields.Datetime.now(),
                        'last_error': str(e)[:2000],
                        'readiness_summary': _('Connection failed.')})
            self._audit(
                'security', f'External server connection failed for {self.name}.',
                severity='critical')
            msg, typ = _('Connection failed: %s', str(e)[:200]), 'danger'
        return self._notify(typ, msg)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_super_admin()
        records = super().create(vals_list)
        for rec in records:
            rec._audit('create', f'External server {rec.name} registered.')
        return records

    def write(self, vals):
        self._check_super_admin()
        if {'host', 'ssh_port'} & set(vals) and any(rec.ssh_host_key_fingerprint for rec in self):
            vals = dict(vals, ssh_host_key_fingerprint=False, ssh_host_key_type=False, state='draft')
        return super().write(vals)

    def unlink(self):
        self._check_super_admin()
        for rec in self:
            active_tenants = rec.tenant_ids.filtered(lambda tenant: tenant.state != 'deleted')
            if active_tenants:
                raise UserError(_(
                    'Server %s cannot be deleted while it has active tenants.', rec.name))
            rec._audit('unlink', f'External server {rec.name} deleted.', severity='warning')
        return super().unlink()
