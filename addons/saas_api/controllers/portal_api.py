from odoo import http
from odoo.http import request


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
        scopes = (post.get('scopes') or 'read').strip()
        tenant_id = request.env.user.tenant_id.id if hasattr(request.env.user, 'tenant_id') else False
        new = request.env['saas.api.token'].sudo().create({
            'name': name, 'user_id': request.env.user.id,
            'tenant_id': tenant_id, 'scopes': scopes,
        })
        return request.render('saas_api.portal_token_created',
                              {'token': new, 'page_name': 'saas_api'})

    @http.route('/my/saas/api-tokens/<int:token_id>/revoke', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def revoke_token(self, token_id, **post):
        t = request.env['saas.api.token'].sudo().browse(token_id)
        if t.exists() and t.user_id.id == request.env.user.id:
            t.action_revoke()
        return request.redirect('/my/saas/api-tokens')
