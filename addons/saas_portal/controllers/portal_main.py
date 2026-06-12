from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import logging

_logger = logging.getLogger(__name__)


class SaasPortalMain(CustomerPortal):

    def _get_my_tenant(self):
        user = request.env.user
        return user.sudo().saas_tenant_id or None

    @http.route(['/my/saas', '/my/saas/dashboard'], type='http', auth='user', website=True)
    def saas_dashboard(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.render('saas_portal.portal_no_tenant', {})
        from odoo.addons.saas_portal.services.portal_service import PortalService
        data = PortalService(request.env).get_dashboard_data(tenant)
        return request.render('saas_portal.portal_dashboard',
                              {'tenant': tenant, 'data': data, 'page_name': 'saas_dashboard'})

    @http.route('/my/saas/access', type='http', auth='user', website=True)
    def saas_access_erp(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        request.env['saas.audit.log'].sudo().log_action(
            model='saas.tenant', record_id=tenant.id, action='login',
            description=f'Customer accessed ERP via portal: {tenant.subdomain}',
            tenant_id=tenant.id, user_id=request.env.user.id)
        return request.redirect(tenant.get_sso_url())

    @http.route('/my/saas/usage', type='http', auth='user', website=True)
    def saas_usage(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        usage = PortalService(request.env).get_usage_data(tenant)
        return request.render('saas_portal.portal_usage',
                              {'tenant': tenant, 'usage': usage, 'page_name': 'saas_usage'})
