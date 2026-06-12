import json
import logging
import os
import re
import secrets
import requests
from odoo import fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 30
PROVISION_REQUEST_DIR = '/mnt/cert-requests'  # Shared volume with the host sweeper.
SUBDOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$')


class ProvisioningBridgeService:
    def __init__(self, env):
        self.env = env
        self._config = None

    @property
    def config(self):
        if not self._config:
            self._config = self.env['saas.config']._get_config()
        return self._config

    def _get_headers(self):
        return {'Authorization': f'Bearer {self.config.api_internal_token}',
                'Content-Type': 'application/json', 'X-Source': 'odoo-saas-core'}

    def _api_url(self, path):
        return f'{self.config.api_base_url.rstrip("/")}{path}'

    def provision(self, tenant):
        job = self.env['saas.provisioning.job'].create({
            'job_type': 'provision', 'tenant_id': tenant.id, 'state': 'pending',
            'payload': json.dumps(self._build_provision_payload(tenant), default=str)})
        job.action_start()
        try:
            result = self._call_provision_api(tenant)
            job.action_complete(result)
            tenant.with_context(bypass_fsm=True).write({'api_instance_id': result.get('instance_id')})
            _logger.info('ProvisioningBridge: tenant %s provisioned (job %d)', tenant.subdomain, job.id)
            return result
        except Exception as e:
            _logger.error('ProvisioningBridge: provision failed for %s: %s', tenant.subdomain, e)
            job.action_fail(str(e), retry=True)
            raise

    def _build_provision_payload(self, tenant):
        allowed_modules = []
        if tenant.plan_id and tenant.plan_id.allowed_modules:
            allowed_modules = [m.strip() for m in tenant.plan_id.allowed_modules.split(',') if m.strip()]
        if not allowed_modules:
            allowed_modules = ['base', 'web']
        return {'subdomain': tenant.subdomain, 'modules': allowed_modules, 'language': 'ar',
                'odoo_version': '19', 'saas_tenant_id': tenant.id,
                'customer_email': tenant.customer_email,
                'company_name': tenant.company_name or tenant.customer_name}

    def _call_provision_api(self, tenant):
        if not self.config.use_api_bridge:
            # Local fallback: drop a provisioning request for the host sweeper
            # to pick up. Creates the Postgres DB + initializes Odoo + issues
            # cert. Returns immediately; the tenant lands in 'pending' until
            # the sweeper sets api_instance_id.
            return self._queue_local_provision(tenant)
        payload = self._build_provision_payload(tenant)
        try:
            resp = requests.post(self._api_url('/api/v1/instances/'), headers=self._get_headers(),
                                 json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise UserError(f'Cannot connect to FastAPI at {self.config.api_base_url}.')
        except requests.exceptions.Timeout:
            raise UserError(f'FastAPI provisioning timed out after {REQUEST_TIMEOUT}s.')
        except requests.exceptions.HTTPError as e:
            try:
                body = e.response.json()
            except Exception:
                body = e.response.text
            raise UserError(f'FastAPI error {e.response.status_code}: {body}')

    def suspend(self, tenant):
        if not tenant.api_instance_id:
            return
        try:
            resp = requests.post(self._api_url(f'/api/v1/instances/{tenant.api_instance_id}/stop'),
                                 headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _logger.error('Bridge suspend failed for %s: %s', tenant.subdomain, e)

    def activate(self, tenant):
        if not tenant.api_instance_id:
            return
        try:
            resp = requests.post(self._api_url(f'/api/v1/instances/{tenant.api_instance_id}/start'),
                                 headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _logger.error('Bridge activate failed for %s: %s', tenant.subdomain, e)

    def delete(self, tenant):
        if not tenant.api_instance_id:
            return
        try:
            resp = requests.delete(self._api_url(f'/api/v1/instances/{tenant.api_instance_id}'),
                                   headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _logger.error('Bridge delete failed for %s: %s', tenant.subdomain, e)

    def _queue_local_provision(self, tenant):
        """Write a JSON request file the host sweeper consumes.

        The sweeper performs three steps for each request:
          1. createdb <subdomain> on the postgres container
          2. docker exec odoo_saas_app odoo -d <sub> -i base,web ...
          3. write a cert-request so HTTPS gets provisioned

        Returns a stub response so the calling code treats it as 'queued'.
        """
        sub = (tenant.subdomain or '').strip().lower()
        if not SUBDOMAIN_RE.match(sub):
            raise UserError(f'Invalid subdomain: {sub!r}')
        if not os.path.isdir(PROVISION_REQUEST_DIR):
            raise UserError(
                f'Local provisioner not installed (missing {PROVISION_REQUEST_DIR}). '
                'Run scripts/install_tenant_provisioner.sh on the host.')
        req_path = os.path.join(PROVISION_REQUEST_DIR, f'{sub}.provision.req')
        done_path = os.path.join(PROVISION_REQUEST_DIR, f'{sub}.provision.done')
        if os.path.exists(done_path):
            _logger.info('Provision already done for %s', sub)
            return {'instance_id': sub, 'status': 'already_provisioned'}
        admin_password = secrets.token_urlsafe(16)
        # Resolve the edition once: prefer the tenant's own field (set at lead
        # creation), fall back to the plan, then default to community. This
        # keeps the host sweeper schema-stable even if we later allow editing.
        edition = (tenant.edition
                   or (tenant.plan_id.edition if tenant.plan_id else None)
                   or 'community')
        # For Enterprise plans the admin may have curated a specific module set
        # (Studio, Helpdesk, Subscriptions, Sign…). Append these to the base
        # modules list so the provisioner installs them on first boot.
        modules = list(self._build_provision_payload(tenant).get('modules', []))
        if edition == 'enterprise' and tenant.plan_id and tenant.plan_id.enterprise_modules:
            ee_modules = [m.strip() for m in tenant.plan_id.enterprise_modules.split(',') if m.strip()]
            for m in ee_modules:
                if m not in modules:
                    modules.append(m)
        # Always install the tenant login helper — it pre-fills email on
        # /web/login from the URL hash we send in the success-page link, so
        # customers don't have to re-type the address.
        if 'saas_tenant_login_helper' not in modules:
            modules.append('saas_tenant_login_helper')
        payload = {
            'subdomain': sub, 'tenant_id': tenant.id,
            'admin_email': tenant.customer_email,
            'admin_name': tenant.customer_name or tenant.company_name or sub,
            'company_name': tenant.company_name or tenant.customer_name or sub,
            'admin_password': admin_password,
            'plan_code': tenant.plan_id.code if tenant.plan_id else 'starter',
            'modules': modules,
            'language': 'ar_001',
            # NEW — host sweeper routes the docker exec to the right container
            # and the cert provisioner picks the right nginx upstream.
            'edition': edition,
        }
        with open(req_path, 'w') as f:
            json.dump(payload, f, ensure_ascii=False)
        _logger.info('Provisioning queued for %s (tenant %s)', sub, tenant.id)
        # Store credentials onto the tenant so admin can retrieve them later.
        # 'api_instance_id' = the new DB name; we'll set it for real when done.
        try:
            tenant.sudo().with_context(bypass_fsm=True).write({
                'api_instance_id': f'pending:{sub}'})
        except Exception:
            pass  # field may be readonly; non-critical
        return {'instance_id': sub, 'status': 'queued',
                'admin_password_one_time': admin_password,
                'message': 'Tenant DB will be created within 2 minutes.'}

    def execute_job(self, job):
        tenant = job.tenant_id
        job.action_start()
        try:
            if job.job_type == 'provision':
                result = self._call_provision_api(tenant)
            elif job.job_type == 'suspend':
                result = self.suspend(tenant) or {}
            elif job.job_type == 'activate':
                result = self.activate(tenant) or {}
            elif job.job_type == 'delete':
                result = self.delete(tenant) or {}
            else:
                raise ValueError(f'Unknown job type: {job.job_type}')
            job.action_complete(result)
        except Exception as e:
            job.action_fail(str(e), retry=True)
            raise
