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

# ── Localization auto-install per signup country ──────────────────────────────
# When a customer picks a country at signup we install that country's official
# Odoo localization (chart of accounts + taxes) plus, where it exists, the
# e-invoicing module. Saudi tenants get ZATCA / Fatoora e-invoicing.
LOCALIZATION_MODULES = {
    'SA': ['l10n_sa', 'l10n_sa_edi'],          # Saudi Arabia + ZATCA e-invoice
    'AE': ['l10n_ae'],
    'EG': ['l10n_eg'],
    'KW': ['l10n_gcc_invoice'],
    'QA': ['l10n_gcc_invoice'],
    'BH': ['l10n_gcc_invoice'],
    'OM': ['l10n_gcc_invoice'],
    'JO': [],
}
# Full Accounting Kit (Cybrosys) — turns the bare `account` app into a complete
# accounting suite. Installed for every tenant so the Accounting app is ready
# the moment the customer logs in.
ACCOUNTING_MODULES = ['base_accounting_kit']
DEFAULT_COUNTRY = 'SA'  # Platform is Saudi-first; fall back to SA if unknown.

# ── Industry app bundles ───────────────────────────────────────────────────────
# The sector the customer picks at signup (homepage cards → ?industry=… →
# signup form) selects which Odoo apps are pre-installed so the workspace is
# ready for their business on first login. All module names below exist in
# Odoo 19 Community. Accounting (account + Full Accounting Kit + country
# localization/ZATCA) is appended separately for every tenant.
INDUSTRY_MODULES = {
    'retail': [
        'point_of_sale',     # نقاط البيع
        'stock',             # المخزون
        'sale_management',   # المبيعات
        'purchase',          # المشتريات
        'crm',               # علاقات العملاء
        'contacts',          # جهات الاتصال
        'hr',                # الموظفون
        'hr_holidays',       # الإجازات
        'hr_attendance',     # الحضور
        'fleet',             # الأسطول
    ],
    'restaurant': [
        'point_of_sale', 'pos_restaurant', 'stock', 'purchase',
        'contacts', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'ecommerce': [
        'website_sale', 'stock', 'sale_management', 'purchase',
        'crm', 'contacts', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'trading': [
        'stock', 'purchase', 'sale_management', 'crm', 'contacts',
        'hr', 'hr_holidays', 'hr_attendance', 'fleet',
    ],
    'construction': [
        'project', 'hr_timesheet', 'stock', 'sale_management', 'purchase',
        'crm', 'contacts', 'hr', 'hr_holidays', 'hr_attendance', 'fleet',
    ],
    'manufacturing': [
        'mrp', 'stock', 'sale_management', 'purchase', 'maintenance',
        'crm', 'contacts', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'services': [
        'project', 'hr_timesheet', 'sale_management', 'crm',
        'contacts', 'hr', 'hr_holidays', 'hr_attendance', 'calendar',
    ],
    # Healthcare/clinics get the full Cybrosys medical suite on top of the
    # generic apps: patient records + doctors + prescriptions
    # (base_hospital_management), dental clinic with interactive dental chart
    # (dental_clinical_management), and lab tests (medical_lab_management).
    # Multi-doctor scheduling comes from `calendar` (one calendar per doctor)
    # and the hospital module's own doctor-allocation screens.
    'healthcare': [
        'calendar', 'crm', 'contacts', 'sale_management', 'purchase',
        'stock', 'hr', 'hr_holidays', 'hr_attendance',
        'base_hospital_management', 'dental_clinical_management',
        'medical_lab_management',
    ],
    'education': [
        'calendar', 'crm', 'contacts', 'sale_management', 'project',
        'hr', 'hr_holidays', 'hr_attendance',
    ],
    'real_estate': [
        'crm', 'contacts', 'sale_management', 'project', 'calendar',
        'hr', 'hr_holidays', 'hr_attendance',
    ],
    'logistics': [
        'stock', 'purchase', 'sale_management', 'fleet',
        'crm', 'contacts', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'hospitality': [
        'point_of_sale', 'pos_restaurant', 'calendar', 'crm', 'contacts',
        'sale_management', 'purchase', 'stock', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'accounting': [
        'contacts', 'crm', 'sale_management', 'project', 'hr_timesheet',
        'hr', 'hr_holidays', 'hr_attendance',
    ],
    'agriculture': [
        'stock', 'purchase', 'sale_management', 'fleet', 'contacts',
        'crm', 'hr', 'hr_holidays', 'hr_attendance',
    ],
    'technology': [
        'project', 'hr_timesheet', 'crm', 'sale_management', 'contacts',
        'hr', 'hr_holidays', 'hr_attendance', 'calendar',
    ],
    'other': [
        'contacts', 'crm', 'sale_management',
    ],
}


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
        # Industry bundle: pre-install the apps matching the sector chosen at
        # signup (retail → POS/Inventory/Sales/Purchase/HR/Fleet, …).
        industry = getattr(tenant, 'industry', None)
        for m in INDUSTRY_MODULES.get(industry or '', []):
            if m not in allowed_modules:
                allowed_modules.append(m)
        return {'subdomain': tenant.subdomain, 'modules': allowed_modules, 'language': 'ar',
                'odoo_version': '19', 'saas_tenant_id': tenant.id,
                'customer_email': tenant.customer_email,
                'company_name': tenant.company_name or tenant.customer_name,
                'industry': industry or ''}

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
        if not self.config.use_api_bridge:
            return self._queue_local_flag(tenant, 'suspend')
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
        if not self.config.use_api_bridge:
            return self._queue_local_flag(tenant, 'resume')
        if not tenant.api_instance_id:
            return
        try:
            resp = requests.post(self._api_url(f'/api/v1/instances/{tenant.api_instance_id}/start'),
                                 headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _logger.error('Bridge activate failed for %s: %s', tenant.subdomain, e)

    def sync_seats(self, tenant):
        """Push the tenant's current seat limit into its live database.

        Writes a <sub>.seats.req file; the host sweeper applies it to the
        tenant's saas.max_users param, which saas_user_limit enforces.
        """
        sub = (tenant.subdomain or '').strip().lower()
        if not SUBDOMAIN_RE.match(sub) or not os.path.isdir(PROVISION_REQUEST_DIR):
            return
        limit = tenant.effective_max_users()
        req_path = os.path.join(PROVISION_REQUEST_DIR, f'{sub}.seats.req')
        with open(req_path, 'w') as f:
            json.dump({'subdomain': sub, 'tenant_id': tenant.id,
                       'max_users': int(limit)}, f)
        _logger.info('Seats sync queued for %s: %s users', sub, limit)
        return {'status': 'seats_queued', 'subdomain': sub, 'max_users': limit}

    def _queue_local_flag(self, tenant, kind):
        """Queue a suspend/resume request for the host sweeper.

        suspend → nginx serves a bilingual "subscription expired" page in
        place of the tenant (the DB stays intact); resume → the original
        proxy config is restored. Both take effect within 2 minutes.
        """
        sub = (tenant.subdomain or '').strip().lower()
        if not SUBDOMAIN_RE.match(sub) or not os.path.isdir(PROVISION_REQUEST_DIR):
            return
        req_path = os.path.join(PROVISION_REQUEST_DIR, f'{sub}.{kind}.req')
        with open(req_path, 'w') as f:
            json.dump({'subdomain': sub, 'tenant_id': tenant.id}, f)
        _logger.info('Tenant %s queued for %s', sub, kind)
        return {'status': f'{kind}_queued', 'subdomain': sub}

    def delete(self, tenant):
        if not self.config.use_api_bridge:
            # Local mode: queue a destruction request for the host sweeper.
            return self._queue_local_delete(tenant)
        if not tenant.api_instance_id:
            return
        try:
            resp = requests.delete(self._api_url(f'/api/v1/instances/{tenant.api_instance_id}'),
                                   headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _logger.error('Bridge delete failed for %s: %s', tenant.subdomain, e)

    def _queue_local_delete(self, tenant):
        """Queue permanent tenant destruction for the host sweeper.

        The sweeper runs saas-tenant-destroyer.sh which takes a final backup
        into /opt/backups/deleted, then drops the database, removes the
        filestore from both Odoo volumes, removes the nginx vhost, revokes
        the SSL cert and cleans the request files. Irreversible from the
        platform's point of view.
        """
        sub = (tenant.subdomain or '').strip().lower()
        if not SUBDOMAIN_RE.match(sub):
            raise UserError(f'Invalid subdomain: {sub!r}')
        if not os.path.isdir(PROVISION_REQUEST_DIR):
            raise UserError(
                f'Local provisioner not installed (missing {PROVISION_REQUEST_DIR}).')
        req_path = os.path.join(PROVISION_REQUEST_DIR, f'{sub}.delete.req')
        payload = {'subdomain': sub, 'tenant_id': tenant.id,
                   'edition': tenant.edition or 'community'}
        with open(req_path, 'w') as f:
            json.dump(payload, f, ensure_ascii=False)
        _logger.warning('Tenant DESTRUCTION queued for %s (tenant %s)', sub, tenant.id)
        return {'status': 'delete_queued', 'subdomain': sub,
                'message': 'Tenant database will be destroyed within 2 minutes.'}

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
        # Accounting + country localization. The customer's chosen country
        # drives which localization (chart of accounts, taxes, e-invoicing) is
        # installed; Saudi tenants get ZATCA e-invoicing. Full Accounting Kit is
        # installed for everyone so the Accounting app is ready out of the box.
        country = (getattr(tenant, 'customer_country', None) or DEFAULT_COUNTRY).upper()
        if 'account' not in modules:
            modules.append('account')  # localization + accounting kit need it
        for m in ACCOUNTING_MODULES + LOCALIZATION_MODULES.get(country, []):
            if m not in modules:
                modules.append(m)
        # Always install the tenant login helper — it pre-fills email on
        # /web/login from the URL hash we send in the success-page link, so
        # customers don't have to re-type the address.
        if 'saas_tenant_login_helper' not in modules:
            modules.append('saas_tenant_login_helper')
        # Always install the user-limit guard — enforces the plan's max_users
        # inside the tenant (reads the saas.max_users param set below).
        if 'saas_user_limit' not in modules:
            modules.append('saas_user_limit')
        payload = {
            'subdomain': sub, 'tenant_id': tenant.id,
            'admin_email': tenant.customer_email,
            'admin_name': tenant.customer_name or tenant.company_name or sub,
            'company_name': tenant.company_name or tenant.customer_name or sub,
            # Signup contact details — the host sweeper writes these into the
            # tenant company (Settings → Companies) so the customer finds their
            # own name/email/phone pre-filled inside their Odoo.
            'company_email': tenant.customer_email or '',
            'company_phone': getattr(tenant, 'phone', '') or '',
            'industry': getattr(tenant, 'industry', '') or '',
            'admin_password': admin_password,
            'plan_code': tenant.plan_id.code if tenant.plan_id else 'starter',
            # Seat limit — the customer's purchased seat count (falls back to
            # the plan's max_users). The host sweeper writes it into the
            # tenant's saas.max_users param, enforced by saas_user_limit.
            'max_users': tenant.effective_max_users(),
            'modules': modules,
            'language': 'ar_001',
            # NEW — host sweeper routes the docker exec to the right container
            # and the cert provisioner picks the right nginx upstream.
            'edition': edition,
            # NEW — host sweeper sets the company's country + currency so the
            # localization's chart of accounts lands on the right company.
            'customer_country': country,
        }
        with open(req_path, 'w') as f:
            json.dump(payload, f, ensure_ascii=False)
        _logger.info('Provisioning queued for %s (tenant %s)', sub, tenant.id)
        # Store credentials onto the tenant so admin can retrieve them later
        # (Tenants form → "Admin Credentials"). The base saas_tenant_manager
        # module already has admin_login/admin_password fields on the form;
        # they were just never populated by the provisioning flow.
        # 'api_instance_id' = the new DB name; we'll set it for real when done.
        try:
            tenant.sudo().with_context(bypass_fsm=True).write({
                'api_instance_id': f'pending:{sub}',
                'admin_login': tenant.customer_email,
                'admin_password': admin_password})
        except Exception:
            _logger.warning('Could not store admin credentials on tenant %s', tenant.id)
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
