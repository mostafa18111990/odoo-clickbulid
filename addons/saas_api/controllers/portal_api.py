from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden


class SaasPortalApi(http.Controller):

    @http.route('/my/saas/api-tokens', type='http', auth='user', website=True)
    def my_tokens(self, **kw):
        tokens = request.env['saas.api.token'].sudo().search([
            ('user_id', '=', request.env.user.id)], order='create_date desc')
        return request.render('saas_api.portal_my_tokens',
                              {'tokens': tokens, 'page_name': 'saas_api'})

    @http.route('/my/saas/api-tokens/new', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def create_token(self, **post):
        name = (post.get('name') or 'API Token').strip()
        user = request.env.user
        tenant = getattr(user, 'saas_tenant_id', False)
        is_platform_admin = user.has_group('saas_core.group_saas_super_admin')
        if not tenant and not is_platform_admin:
            raise Forbidden('A SaaS tenant is required to create an API token.')

        requested_scopes = {
            scope.strip() for scope in (post.get('scopes') or 'read').split(',')
            if scope.strip()
        }
        allowed_scopes = {'read', 'write', 'admin'} if is_platform_admin else {'read'}
        scopes = ','.join(sorted(requested_scopes & allowed_scopes)) or 'read'
        new = request.env['saas.api.token'].sudo().create({
            'name': name, 'user_id': user.id,
            'tenant_id': tenant.id if tenant else False, 'scopes': scopes,
        })
        plain_token = new.plain_token_once
        response = request.render('saas_api.portal_token_created', {
            'token': new,
            'plain_token': plain_token,
            'page_name': 'saas_api',
        })
        response.flatten()
        new.write({'plain_token_once': False})
        return response

    @http.route('/my/saas/api-tokens/<int:token_id>/revoke', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def revoke_token(self, token_id, **post):
        t = request.env['saas.api.token'].sudo().browse(token_id)
        if t.exists() and t.user_id.id == request.env.user.id:
            t.action_revoke()
        return request.redirect('/my/saas/api-tokens')
