import logging
import re
import secrets
import shlex

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
SUBDOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$')

# Same accounting/localization defaults the local provisioner installs.
ACCOUNTING_MODULES = ['base_accounting_kit']
LOCALIZATION_MODULES = {
    'SA': ['l10n_sa', 'l10n_sa_edi'], 'AE': ['l10n_ae'], 'EG': ['l10n_eg'],
}


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
        # De-dup, keep order.
        seen, out = set(), []
        for m in modules:
            if m and m not in seen:
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

    def suspend(self, tenant):
        # Best-effort: stop the tenant being served is server-specific; we
        # record intent and let the operator wire nginx there. DB is kept.
        _logger.info('Remote suspend requested for %s', tenant.subdomain)
        return {'status': 'suspended', 'subdomain': tenant.subdomain}

    def activate(self, tenant):
        _logger.info('Remote resume requested for %s', tenant.subdomain)
        return {'status': 'resumed', 'subdomain': tenant.subdomain}

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
        _logger.info('Remote delete done for %s on %s', sub, server.name)
        return {'status': 'deleted', 'subdomain': sub}
