import logging
import requests

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 180


class AppInstallBridge:
    def __init__(self, env):
        self.env = env
        self._config = None

    @property
    def config(self):
        if not self._config:
            self._config = self.env['saas.config'].sudo()._get_config()
        return self._config

    def _headers(self):
        return {'Authorization': f'Bearer {self.config.api_internal_token}',
                'Content-Type': 'application/json', 'X-Source': 'odoo-saas-marketplace'}

    def _url(self, path):
        return f'{self.config.api_base_url.rstrip("/")}{path}'

    def install_module(self, tenant, module):
        if not self.config.use_api_bridge:
            return {'success': False, 'error': 'API bridge disabled'}
        payload = {'tenant_db': tenant.db_name, 'tenant_subdomain': tenant.subdomain,
                   'module': module, 'api_instance_id': tenant.api_instance_id}
        try:
            resp = requests.post(
                self._url(f'/api/v1/tenants/{tenant.api_instance_id}/apps/install'),
                headers=self._headers(), json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return {'success': data.get('success', False), 'job_id': data.get('job_id'),
                    'error': data.get('error')}
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Install timed out', 'pending': True}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Cannot connect to provisioning engine'}
        except Exception as e:
            _logger.error('Module install failed for %s/%s: %s', tenant.subdomain, module, e)
            return {'success': False, 'error': str(e)}

    def uninstall_module(self, tenant, module):
        if not self.config.use_api_bridge:
            return {'success': False, 'error': 'API bridge disabled'}
        try:
            resp = requests.post(
                self._url(f'/api/v1/tenants/{tenant.api_instance_id}/apps/uninstall'),
                headers=self._headers(),
                json={'tenant_db': tenant.db_name, 'module': module}, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return {'success': data.get('success', False), 'error': data.get('error')}
        except Exception as e:
            _logger.error('Module uninstall failed for %s/%s: %s', tenant.subdomain, module, e)
            return {'success': False, 'error': str(e)}
