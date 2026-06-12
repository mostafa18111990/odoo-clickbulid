from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain


class SaasPortalAccount(SaasPortalMain):

    @http.route('/my/saas/account', type='http', auth='user', website=True)
    def saas_account(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        return request.render('saas_portal.portal_account',
                              {'tenant': tenant, 'user': request.env.user, 'page_name': 'saas_account'})

    @http.route('/my/saas/account/update', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_account_update(self, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        allowed = {}
        if post.get('customer_name'):
            allowed['customer_name'] = post['customer_name']
        if post.get('phone'):
            allowed['phone'] = post['phone']
        if post.get('company_name'):
            allowed['company_name'] = post['company_name']
        if allowed:
            tenant.sudo().with_context(bypass_fsm=True).write(allowed)
        return request.redirect('/my/saas/account?updated=1')
