import base64
import logging
import re
import secrets
import shlex
import socket

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
SUBDOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$')

# Same accounting/localization defaults the local provisioner installs.
ACCOUNTING_MODULES = ['base_accounting_kit']
LOCALIZATION_MODULES = {
    'SA': ['l10n_sa', 'l10n_sa_edi'], 'AE': ['l10n_ae'], 'EG': ['l10n_eg'],
}
AUTO_INSTALL_EXCLUDED_MODULES = {'trailer_inspection_saso'}


class RemoteProvisioningService:
    """Provision / suspend / delete a tenant on an external server over SSH.

    Mirrors scripts/install_tenant_provisioner.sh but runs each step as a
    `docker exec` on the customer's server through the server's SSH session.
    """

    def __init__(self, env):
        self.env = env

    # ── helpers ─────────────────────────────────────────────────────────────
    def _modules_for(self, tenant):
        modules = ['base', 'web', 'mail', 'account']
        if tenant.plan_id and tenant.plan_id.allowed_modules:
            modules += [m.strip() for m in tenant.plan_id.allowed_modules.split(',') if m.strip()]
        # Industry bundle (reuse the core mapping if available).
        try:
            from odoo.addons.saas_core.services.provisioning_bridge import INDUSTRY_MODULES
            modules += INDUSTRY_MODULES.get(getattr(tenant, 'industry', '') or '', [])
        except Exception:
            pass
        country = (getattr(tenant, 'customer_country', None) or 'SA').upper()[:2]
        modules += ACCOUNTING_MODULES + LOCALIZATION_MODULES.get(country, [])
        # Seat-limit guard, same as the local platform tenants get.
        modules.append('saas_user_limit')
        # De-dup, keep order.
        seen, out = set(), []
        for m in modules:
            if m and m not in AUTO_INSTALL_EXCLUDED_MODULES and m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def _docker_odoo(self, server, db, args):
        return (f'docker exec {shlex.quote(server.odoo_container)} odoo '
                f'--config=/etc/odoo/odoo.conf -d {shlex.quote(db)} {args} '
                f'--no-http --stop-after-init')

    def _psql(self, server, db, sql):
        return (f'docker exec {shlex.quote(server.postgres_container)} '
                f'psql -U {shlex.quote(server.postgres_user)} -d {shlex.quote(db)} '
                f'-tAc {shlex.quote(sql)}')

    # ── provision ───────────────────────────────────────────────────────────
    def provision(self, tenant):
        server = tenant.external_server_id
        if not server:
            raise UserError('Tenant has no external server assigned.')
        sub = (tenant.subdomain or '').strip().lower()
        if not SUBDOMAIN_RE.match(sub):
            raise UserError(f'Invalid subdomain: {sub!r}')
        if server.state != 'online':
            raise UserError(f'External server {server.name!r} is not online.')
        if server.tenant_count > server.max_tenants:
            raise UserError(
                f'External server {server.name!r} has reached its tenant capacity.')

        fqdn = f'{sub}.{server.base_domain}'
        try:
            resolved = socket.gethostbyname(fqdn)
            target = socket.gethostbyname(server.host)
        except OSError as exc:
            raise UserError(
                f'DNS for {fqdn} is not ready. Point it to the dedicated server first.') from exc
        if resolved != target:
            raise UserError(
                f'DNS for {fqdn} resolves to {resolved}, but the server resolves to {target}.')

        admin_password = secrets.token_urlsafe(16)
        modules = self._modules_for(tenant)
        country = (getattr(tenant, 'customer_country', None) or 'SA').upper()[:2]

        # 1. createdb (skip if present) owned by the community role.
        check = server.run_ssh(
            f'docker exec {server.postgres_container} psql -U {server.postgres_user} '
            f'-lqt | cut -d"|" -f1 | tr -d " " | grep -qx {shlex.quote(sub)} '
            f'&& echo EXISTS || echo NEW', raise_on_error=False)[1]
        if 'EXISTS' not in check:
            server.run_ssh(
                f'docker exec {server.postgres_container} createdb '
                f'-U {server.postgres_user} -O {shlex.quote(server.db_owner)} {shlex.quote(sub)}')

        # 2. init odoo with the module set.
        server.run_ssh(self._docker_odoo(
            server, sub, f'-i {shlex.quote(",".join(modules))} --without-demo=all --load-language=ar_001'))

        # 3. configure the admin user + company via a remote python one-liner.
        py = (
            "import os,odoo;from odoo.tools import config;"
            "config.parse_config(['-c','/etc/odoo/odoo.conf']);"
            "reg=odoo.modules.registry.Registry(os.environ['D']);"
            "cr=reg.cursor();env=odoo.api.Environment(cr,1,{});"
            "u=env['res.users'].browse(2);"
            "u.write({'login':os.environ['E'],'name':os.environ['N'],'password':os.environ['P']});"
            "c=u.company_id;c.write({'name':os.environ['CO'],'email':os.environ['E']});"
            "co=env['res.country'].search([('code','=',os.environ['CC'])],limit=1);"
            "c.write({'country_id':co.id,'currency_id':co.currency_id.id}) if co and co.currency_id else None;"
            "cr.commit();print('OK')")
        env_prefix = (
            f'docker exec -e D={shlex.quote(sub)} -e E={shlex.quote(tenant.customer_email or "")} '
            f'-e N={shlex.quote(tenant.customer_name or sub)} -e P={shlex.quote(admin_password)} '
            f'-e CO={shlex.quote(tenant.company_name or tenant.customer_name or sub)} '
            f'-e CC={shlex.quote(country)} {server.odoo_container} python3 -c {shlex.quote(py)}')
        server.run_ssh(env_prefix)

        # Enforce the purchased seat count inside the remote tenant DB.
        self._set_remote_seats(server, sub, tenant.effective_max_users())
        self._configure_tenant_route(server, sub)

        _logger.info('Remote provision done for %s on %s', sub, server.name)
        tenant.sudo().with_context(bypass_fsm=True).write({
            'api_instance_id': f'remote:{server.id}:{sub}',
            'admin_login': tenant.customer_email,
            'admin_password': admin_password,
            'state': 'trial' if tenant.state == 'lead' else tenant.state,
        })
        return {'status': 'provisioned', 'subdomain': sub,
                'admin_password_one_time': admin_password,
                'url': f'https://{sub}.{server.base_domain}'}

    def _configure_tenant_route(self, server, sub):
        """Create HTTP challenge route, issue TLS, then activate HTTPS proxy."""
        fqdn = f'{sub}.{server.base_domain}'
        root = server.ROOT
        http_conf = f'''server {{
    listen 80;
    server_name {fqdn};
    location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
    location / {{ proxy_pass http://{server.odoo_container}:8069; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Real-IP $remote_addr; }}
}}
'''
        http_b64 = base64.b64encode(http_conf.encode()).decode()
        conf_path = f'{root}/nginx-tenants/{sub}.conf'
        server.run_ssh(
            f'echo {shlex.quote(http_b64)} | base64 -d > {shlex.quote(conf_path)} && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -t && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -s reload')
        email = server.letsencrypt_email or 'sales@clickbuild.com'
        server.run_ssh(
            'command -v certbot >/dev/null 2>&1 || '
            '(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot); '
            f'certbot certonly --webroot -w {shlex.quote(root + "/certbot/www")} '
            f'-d {shlex.quote(fqdn)} --email {shlex.quote(email)} '
            '--agree-tos --non-interactive --keep-until-expiring')
        https_conf = f'''server {{
    listen 80;
    server_name {fqdn};
    location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
    location / {{ return 301 https://$host$request_uri; }}
}}
server {{
    listen 443 ssl http2;
    server_name {fqdn};
    ssl_certificate /etc/letsencrypt/live/{fqdn}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{fqdn}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 200m;
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    location /websocket {{
        proxy_pass http://{server.odoo_container}:8072;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}
    location / {{
        proxy_pass http://{server.odoo_container}:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
'''
        https_b64 = base64.b64encode(https_conf.encode()).decode()
        server.run_ssh(
            f'echo {shlex.quote(https_b64)} | base64 -d > {shlex.quote(conf_path)} && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -t && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -s reload')

    def _suspended_conf(self, server, sub):
        """The nginx server block that replaces a suspended tenant's proxy
        with a bilingual 'subscription expired' page (HTTP 402)."""
        fqdn = f'{sub}.{server.base_domain}'
        page = (
            '<!doctype html><html dir=\\"rtl\\" lang=\\"ar\\"><head><meta charset=\\"utf-8\\">'
            '<title>الاشتراك منتهي</title><style>body{font-family:Tahoma,Arial;background:#f5f3ff;'
            'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}'
            '.c{background:#fff;border-radius:16px;padding:48px;max-width:520px;text-align:center;'
            'box-shadow:0 10px 40px rgba(109,40,217,.12)}h1{color:#6d28d9}a{display:inline-block;'
            'background:#6d28d9;color:#fff;text-decoration:none;padding:14px 36px;border-radius:10px;'
            'font-weight:bold;margin-top:18px}</style></head><body><div class=\\"c\\">'
            '<div style=\\"font-size:3rem\\">⏸️</div><h1>انتهت الفترة التجريبية / الاشتراك</h1>'
            '<p>تم إيقاف مساحة العمل مؤقتاً. بياناتك محفوظة — جدّد الآن لاستعادة الوصول.</p>'
            '<p style=\\"direction:ltr\\">Your workspace is paused. Your data is safe — renew to restore access.</p>'
            f'<a href=\\"https://{server.base_domain}/pricing\\">جدّد الآن — Renew Now</a></div></body></html>'
        )
        return (
            'server {\n'
            '    listen 443 ssl http2;\n'
            f'    server_name {fqdn};\n'
            f'    ssl_certificate     /etc/letsencrypt/live/{fqdn}/fullchain.pem;\n'
            f'    ssl_certificate_key /etc/letsencrypt/live/{fqdn}/privkey.pem;\n'
            '    ssl_protocols TLSv1.2 TLSv1.3;\n'
            '    location / {\n'
            '        default_type "text/html; charset=utf-8";\n'
            f'        return 402 "{page}";\n'
            '    }\n'
            '}\n'
        )

    def _set_remote_seats(self, server, sub, limit):
        """Write the seat limit into the remote tenant's saas.max_users param."""
        py = (
            "import os,odoo;from odoo.tools import config;"
            "config.parse_config(['-c','/etc/odoo/odoo.conf']);"
            "reg=odoo.modules.registry.Registry(os.environ['D']);"
            "cr=reg.cursor();env=odoo.api.Environment(cr,1,{});"
            "env['ir.config_parameter'].sudo().set_param('saas.max_users',os.environ['L']);"
            "cr.commit();print('SEATS_OK')")
        cmd = (f'docker exec -e D={shlex.quote(sub)} -e L={shlex.quote(str(int(limit)))} '
               f'{server.odoo_container} python3 -c {shlex.quote(py)}')
        server.run_ssh(cmd, raise_on_error=False)

    def sync_seats(self, tenant):
        """Push the tenant's current seat limit to the remote DB (admin edit)."""
        server = tenant.external_server_id
        sub = (tenant.subdomain or '').strip().lower()
        if not server or not SUBDOMAIN_RE.match(sub):
            return
        self._set_remote_seats(server, sub, tenant.effective_max_users())
        return {'status': 'seats_synced', 'subdomain': sub}

    def suspend(self, tenant):
        """Swap the remote nginx vhost for the renewal page (DB kept)."""
        server = tenant.external_server_id
        sub = (tenant.subdomain or '').strip().lower()
        if not server or not SUBDOMAIN_RE.match(sub):
            return
        import base64
        conf_b64 = base64.b64encode(self._suspended_conf(server, sub).encode()).decode()
        d = '/opt/odoo-saas/nginx-tenants'
        # Back up the live conf once, write the block page, reload nginx.
        cmd = (
            f'[ -f {d}/{sub}.conf ] && [ ! -f {d}/{sub}.conf.live-orig ] && '
            f'cp {d}/{sub}.conf {d}/{sub}.conf.live-orig; '
            f'echo {conf_b64} | base64 -d > {d}/{sub}.conf && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -t 2>/dev/null && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -s reload'
        )
        server.run_ssh(cmd, raise_on_error=False)
        _logger.info('Remote suspend applied for %s on %s', sub, server.name)
        return {'status': 'suspended', 'subdomain': sub}

    def activate(self, tenant):
        """Restore the remote tenant's original proxy vhost."""
        server = tenant.external_server_id
        sub = (tenant.subdomain or '').strip().lower()
        if not server or not SUBDOMAIN_RE.match(sub):
            return
        d = '/opt/odoo-saas/nginx-tenants'
        cmd = (
            f'[ -f {d}/{sub}.conf.live-orig ] && '
            f'mv {d}/{sub}.conf.live-orig {d}/{sub}.conf && '
            f'docker exec {shlex.quote(server.nginx_container)} nginx -s reload'
        )
        server.run_ssh(cmd, raise_on_error=False)
        _logger.info('Remote resume applied for %s on %s', sub, server.name)
        return {'status': 'resumed', 'subdomain': sub}

    def delete(self, tenant):
        """Drop the remote DB (with a backup) + filestore."""
        server = tenant.external_server_id
        sub = (tenant.subdomain or '').strip().lower()
        if not server or not SUBDOMAIN_RE.match(sub):
            return
        ts_cmd = 'date -u +%Y%m%d_%H%M%S'
        server.run_ssh(
            f'mkdir -p /opt/backups/deleted && '
            f'docker exec {server.postgres_container} pg_dump -U {server.postgres_user} {shlex.quote(sub)} '
            f'| gzip -1 > /opt/backups/deleted/{shlex.quote(sub)}_DELETED_$({ts_cmd}).sql.gz',
            raise_on_error=False)
        server.run_ssh(
            f'docker exec {server.postgres_container} dropdb -U {server.postgres_user} --force --if-exists {shlex.quote(sub)}',
            raise_on_error=False)
        server.run_ssh(
            f'docker exec {server.odoo_container} rm -rf /var/lib/odoo/filestore/{shlex.quote(sub)}',
            raise_on_error=False)
        server.run_ssh(
            f'rm -f {server.ROOT}/nginx-tenants/{shlex.quote(sub)}.conf '
            f'{server.ROOT}/nginx-tenants/{shlex.quote(sub)}.conf.live-orig && '
            f'docker exec {server.nginx_container} nginx -t && '
            f'docker exec {server.nginx_container} nginx -s reload',
            raise_on_error=False)
        _logger.info('Remote delete done for %s on %s', sub, server.name)
        return {'status': 'deleted', 'subdomain': sub}
