from odoo import http, fields
from odoo.http import request, Response
import json
import time
import logging

_logger = logging.getLogger(__name__)


def _json_response(data, status=200):
    return Response(json.dumps(data, default=str),
                    content_type='application/json', status=status)


class SaasApiV1(http.Controller):

    @staticmethod
    def _is_platform_admin(token):
        return bool(
            token
            and token.user_id
            and token.user_id.has_group('saas_core.group_saas_super_admin')
        )

    def _authenticate(self, required_scope='read'):
        from odoo.addons.saas_api.services.token_service import TokenService
        from odoo.addons.saas_api.services.rate_limit_service import RateLimitService
        auth = request.httprequest.headers.get('Authorization') or \
            request.httprequest.headers.get('X-Api-Token')
        token = TokenService(request.env(su=True)).validate_token(auth)
        if not token:
            return None, _json_response({'error': 'unauthorized'}, 401)
        if required_scope and not token.has_scope(required_scope):
            return None, _json_response({'error': 'insufficient_scope'}, 403)
        if not token.tenant_id and not self._is_platform_admin(token):
            return None, _json_response({'error': 'tenant_scope_required'}, 403)
        if not RateLimitService(request.env(su=True)).check(token):
            return None, _json_response({'error': 'rate_limit_exceeded'}, 429)
        TokenService(request.env(su=True)).touch(
            token, ip_address=request.httprequest.remote_addr)
        return token, None

    def _log(self, token, endpoint, status, response_time_ms, error=None):
        try:
            request.env['saas.api.request.log'].sudo().create({
                'token_id': token.id if token else False,
                'user_id': token.user_id.id if token else False,
                'tenant_id': token.tenant_id.id if token and token.tenant_id else False,
                'endpoint': endpoint,
                'method': request.httprequest.method,
                'status_code': status,
                'response_time_ms': response_time_ms,
                'ip_address': request.httprequest.remote_addr or '',
                'user_agent': request.httprequest.headers.get('User-Agent', '')[:200],
                'error_message': error or '',
            })
        except Exception:
            _logger.exception('API log failure')

    def _handle(self, endpoint, handler, required_scope='read'):
        t0 = time.time()
        token, err = self._authenticate(required_scope=required_scope)
        if err:
            self._log(None, endpoint, err.status_code,
                      int((time.time() - t0) * 1000),
                      error=err.response[0].decode() if err.response else '')
            return err
        try:
            response = handler(token)
            self._log(token, endpoint, response.status_code,
                      int((time.time() - t0) * 1000))
            return response
        except Exception as e:
            _logger.exception('API handler error')
            self._log(token, endpoint, 500, int((time.time() - t0) * 1000), error=str(e))
            return _json_response({'error': 'internal_error'}, 500)

    @http.route('/api/v1/me', type='http', auth='none', csrf=False, methods=['GET'])
    def me(self, **kw):
        def handler(token):
            return _json_response({
                'user_id': token.user_id.id,
                'user_name': token.user_id.name,
                'user_email': token.user_id.email,
                'tenant_id': token.tenant_id.id if token.tenant_id else None,
                'tenant_name': token.tenant_id.name if token.tenant_id else None,
                'scopes': token.scopes,
                'token_name': token.name,
            })
        return self._handle('/api/v1/me', handler)

    @http.route('/api/v1/tenants', type='http', auth='none', csrf=False, methods=['GET'])
    def list_tenants(self, **kw):
        def handler(token):
            if token.tenant_id:
                tenants = token.tenant_id
            else:
                if not self._is_platform_admin(token):
                    return _json_response({'error': 'forbidden'}, 403)
                tenants = request.env['saas.tenant'].sudo().search([], limit=100)
            return _json_response({'data': [{
                'id': t.id, 'name': t.name, 'subdomain': t.subdomain,
                'state': t.state, 'plan_id': t.plan_id.id if t.plan_id else None,
            } for t in tenants]})
        return self._handle('/api/v1/tenants', handler)

    @http.route('/api/v1/tenants/<int:tenant_id>', type='http', auth='none',
                csrf=False, methods=['GET'])
    def get_tenant(self, tenant_id, **kw):
        def handler(token):
            if token.tenant_id and token.tenant_id.id != tenant_id:
                return _json_response({'error': 'forbidden'}, 403)
            if not token.tenant_id and not self._is_platform_admin(token):
                return _json_response({'error': 'forbidden'}, 403)
            t = request.env['saas.tenant'].sudo().browse(tenant_id)
            if not t.exists():
                return _json_response({'error': 'not_found'}, 404)
            return _json_response({
                'id': t.id, 'name': t.name, 'subdomain': t.subdomain,
                'state': t.state, 'created_at': t.create_date,
                'plan': t.plan_id.name if t.plan_id else None,
            })
        return self._handle(f'/api/v1/tenants/{tenant_id}', handler)

    @http.route('/api/v1/subscriptions', type='http', auth='none',
                csrf=False, methods=['GET'])
    def list_subscriptions(self, **kw):
        def handler(token):
            domain = []
            if token.tenant_id:
                domain.append(('tenant_id', '=', token.tenant_id.id))
            elif not self._is_platform_admin(token):
                return _json_response({'error': 'forbidden'}, 403)
            subs = request.env['saas.subscription'].sudo().search(domain, limit=100)
            return _json_response({'data': [{
                'id': s.id, 'tenant_id': s.tenant_id.id if s.tenant_id else None,
                'plan_id': s.plan_id.id if s.plan_id else None,
                'status': s.status, 'amount': s.amount,
            } for s in subs]})
        return self._handle('/api/v1/subscriptions', handler)

    @http.route('/api/v1/invoices', type='http', auth='none',
                csrf=False, methods=['GET'])
    def list_invoices(self, **kw):
        def handler(token):
            domain = []
            if token.tenant_id:
                domain.append(('tenant_id', '=', token.tenant_id.id))
            elif not self._is_platform_admin(token):
                return _json_response({'error': 'forbidden'}, 403)
            invoices = request.env['saas.invoice'].sudo().search(domain, limit=100)
            return _json_response({'data': [{
                'id': i.id, 'name': i.name, 'amount_total': i.amount_total,
                'state': i.state, 'invoice_date': i.invoice_date,
            } for i in invoices]})
        return self._handle('/api/v1/invoices', handler)

    @http.route('/api/v1/health', type='http', auth='none', csrf=False, methods=['GET'])
    def health(self, **kw):
        return _json_response({'status': 'ok', 'time': fields.Datetime.now()})
