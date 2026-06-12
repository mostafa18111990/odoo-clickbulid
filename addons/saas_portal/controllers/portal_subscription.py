from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain
import logging

_logger = logging.getLogger(__name__)


class SaasPortalSubscription(SaasPortalMain):

    @http.route('/my/saas/subscription', type='http', auth='user', website=True)
    def saas_subscription(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        sub_data = PortalService(request.env).get_subscription_data(tenant)
        return request.render('saas_portal.portal_subscription',
                              {'tenant': tenant, 'sub': sub_data, 'page_name': 'saas_subscription'})

    @http.route('/my/saas/subscription/plans', type='http', auth='user', website=True)
    def saas_plans(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        plans = PortalService(request.env).get_available_plans(tenant)
        return request.render('saas_portal.portal_plans',
                              {'tenant': tenant, 'plans': plans, 'page_name': 'saas_plans'})

    @http.route('/my/saas/subscription/upgrade', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_upgrade(self, plan_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            result = PortalService(request.env).request_upgrade(tenant, int(plan_id))
            if result.get('requires_payment') and result.get('checkout_url'):
                return request.redirect(result['checkout_url'])
            return request.redirect('/my/saas/subscription?upgrade=success')
        except Exception as e:
            return request.redirect(f'/my/saas/subscription/plans?error={e}')

    @http.route('/my/saas/subscription/downgrade', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_downgrade(self, plan_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            PortalService(request.env).request_downgrade(tenant, int(plan_id))
            return request.redirect('/my/saas/subscription?downgrade=scheduled')
        except Exception as e:
            return request.redirect(f'/my/saas/subscription/plans?error={e}')

    @http.route('/my/saas/subscription/cycle', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_change_cycle(self, cycle, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            PortalService(request.env).request_cycle_change(tenant, cycle)
            return request.redirect('/my/saas/subscription?cycle=changed')
        except Exception as e:
            return request.redirect(f'/my/saas/subscription?error={e}')

    @http.route('/my/saas/subscription/cancel', type='http', auth='user', website=True)
    def saas_cancel_page(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        reasons = request.env['saas.cancellation.reason'].sudo().search([('active', '=', True)])
        return request.render('saas_portal.portal_cancel',
                              {'tenant': tenant, 'reasons': reasons, 'page_name': 'saas_cancel'})

    @http.route('/my/saas/subscription/cancel/confirm', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_cancel_confirm(self, reason_code=None, note=None, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            PortalService(request.env).request_cancel(tenant, reason_code, note)
            return request.redirect('/my/saas/subscription?cancelled=1')
        except Exception as e:
            return request.redirect(f'/my/saas/subscription?error={e}')
