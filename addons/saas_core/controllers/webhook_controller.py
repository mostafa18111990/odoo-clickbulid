from odoo import http
from odoo.http import request
import json
import hmac
import hashlib
import logging

_logger = logging.getLogger(__name__)


class SaasCoreWebhookController(http.Controller):

    def _validate_signature(self, body, signature):
        try:
            config = request.env['saas.config'].sudo()._get_config()
            secret = config.webhook_secret.encode('utf-8')
            expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(f'sha256={expected}', signature or '')
        except Exception as e:
            _logger.error('Webhook signature validation error: %s', e)
            return False

    def _parse_and_validate(self):
        body = request.httprequest.get_data()
        signature = request.httprequest.headers.get('X-SaaS-Signature', '')
        if not self._validate_signature(body, signature):
            return None, {'error': 'Invalid signature', 'status': 401}
        try:
            return json.loads(body), None
        except json.JSONDecodeError:
            return None, {'error': 'Invalid JSON', 'status': 400}

    @http.route('/saas/core/webhook/provisioning', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def provisioning_webhook(self, **kwargs):
        data, err = self._parse_and_validate()
        if err:
            return err
        event = data.get('event')
        subdomain = data.get('subdomain')
        saas_tenant_id = data.get('saas_tenant_id')
        env = request.env(su=True)
        tenant = None
        if saas_tenant_id:
            tenant = env['saas.tenant'].browse(int(saas_tenant_id)).exists()
        if not tenant and subdomain:
            tenant = env['saas.tenant'].search([('subdomain', '=', subdomain)], limit=1)
        if not tenant:
            return {'status': 'ignored', 'reason': 'tenant not found'}
        if event == 'provisioning.completed':
            return self._handle_provision_completed(env, tenant, data)
        elif event == 'provisioning.failed':
            return self._handle_provision_failed(env, tenant, data)
        return {'status': 'ignored', 'reason': f'unknown event: {event}'}

    def _handle_provision_completed(self, env, tenant, data):
        tenant.with_context(bypass_fsm=True).write({
            'api_instance_id': data.get('instance_id'),
            'db_name': data.get('db_name') or tenant.db_name,
            'tenant_url': data.get('url') or tenant.tenant_url})
        job = env['saas.provisioning.job'].search([
            ('tenant_id', '=', tenant.id), ('job_type', '=', 'provision'),
            ('state', '=', 'running')], limit=1)
        if job:
            job.action_complete(data)
        env['saas.event']._publish('provisioning.completed', model='saas.tenant',
                                   record_id=tenant.id, payload=data, tenant_id=tenant.id)
        return {'status': 'ok'}

    def _handle_provision_failed(self, env, tenant, data):
        error = data.get('error', 'Unknown error')
        job = env['saas.provisioning.job'].search([
            ('tenant_id', '=', tenant.id), ('job_type', '=', 'provision'),
            ('state', '=', 'running')], limit=1)
        if job:
            job.action_fail(error, retry=True)
        env['saas.event']._publish('provisioning.failed', model='saas.tenant',
                                   record_id=tenant.id, payload=data, tenant_id=tenant.id)
        return {'status': 'ok'}
