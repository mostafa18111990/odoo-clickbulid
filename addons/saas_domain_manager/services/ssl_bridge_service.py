import logging
import os
import re
import requests

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 60
CERT_REQUEST_DIR = '/mnt/cert-requests'
SUBDOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$')


class SslBridgeService:
    def __init__(self, env):
        self.env = env
        self._config = None

    def request_tenant_subdomain_cert(self, tenant):
        """Drop a cert-request file for the host-side sweeper to pick up.

        Idempotent: if cert already exists (.done flag) or request is pending
        (.req exists), this is a no-op. The sweeper systemd timer (every 2 min)
        runs ``provision_tenant_cert.sh`` and writes ``.done`` or ``.error``.
        Returns (queued: bool, reason: str).
        """
        if not tenant or not tenant.subdomain:
            return False, 'no subdomain'
        sub = tenant.subdomain.strip().lower()
        if not SUBDOMAIN_RE.match(sub):
            _logger.warning('Invalid subdomain for cert request: %r', sub)
            return False, 'invalid subdomain'
        if not os.path.isdir(CERT_REQUEST_DIR):
            _logger.warning('Cert-request dir %s missing — sweeper not installed?',
                            CERT_REQUEST_DIR)
            return False, 'sweeper not installed'
        done = os.path.join(CERT_REQUEST_DIR, f'{sub}.done')
        req = os.path.join(CERT_REQUEST_DIR, f'{sub}.req')
        if os.path.exists(done):
            return False, 'already done'
        if os.path.exists(req):
            return False, 'already queued'
        try:
            with open(req, 'w') as f:
                f.write(f'tenant_id={tenant.id}\nsubdomain={sub}\n')
            _logger.info('Cert request queued for %s.clickbulid.com (tenant %s)',
                         sub, tenant.id)
            return True, 'queued'
        except Exception as e:
            _logger.error('Cannot write cert request for %s: %s', sub, e)
            return False, str(e)

    @property
    def config(self):
        if not self._config:
            self._config = self.env['saas.config'].sudo()._get_config()
        return self._config

    def _headers(self):
        return {'Authorization': f'Bearer {self.config.api_internal_token}',
                'Content-Type': 'application/json', 'X-Source': 'odoo-saas-domain-manager'}

    def _url(self, path):
        return f'{self.config.api_base_url.rstrip("/")}{path}'

    def issue_ssl(self, domain):
        if not self.config.use_api_bridge:
            return {'success': False, 'error': 'API bridge disabled'}
        payload = {'domain': domain.domain, 'tenant_subdomain': domain.tenant_id.subdomain,
                   'tenant_port': getattr(domain.tenant_id, 'odoo_port', None), 'saas_domain_id': domain.id}
        try:
            resp = requests.post(self._url('/api/v1/domains/ssl/issue'), headers=self._headers(),
                                 json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return {'success': data.get('success', False), 'expires_at': data.get('expires_at'),
                    'error': data.get('error')}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Cannot connect to provisioning engine'}
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'SSL issuance timed out'}
        except Exception as e:
            _logger.error('SSL issuance failed for %s: %s', domain.domain, e)
            return {'success': False, 'error': str(e)}

    def remove_domain(self, domain):
        if not self.config.use_api_bridge:
            return {'success': True, 'note': 'API bridge disabled, skipped'}
        try:
            resp = requests.delete(self._url(f'/api/v1/domains/{domain.domain}'),
                                   headers=self._headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return {'success': True}
        except Exception as e:
            _logger.error('Domain removal failed for %s: %s', domain.domain, e)
            return {'success': False, 'error': str(e)}

    def renew_ssl(self, domain):
        try:
            resp = requests.post(self._url('/api/v1/domains/ssl/renew'), headers=self._headers(),
                                 json={'domain': domain.domain}, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return {'success': data.get('success', False), 'expires_at': data.get('expires_at')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
