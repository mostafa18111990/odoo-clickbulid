from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain
import logging

_logger = logging.getLogger(__name__)


class SaasPortalMarketplace(SaasPortalMain):

    @http.route(['/my/saas/marketplace',
                 '/my/saas/marketplace/category/<string:category>'],
                type='http', auth='user', website=True)
    def marketplace(self, category=None, search=None, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_marketplace.services.marketplace_service import MarketplaceService
        apps = MarketplaceService(request.env(su=True)).get_catalog(tenant, category, search)
        categories = request.env['saas.marketplace.category'].sudo().search([('active', '=', True)])
        return request.render('saas_marketplace.portal_marketplace', {
            'tenant': tenant, 'apps': apps, 'categories': categories,
            'current_category': category, 'search': search or '', 'page_name': 'saas_marketplace'})

    @http.route('/my/saas/marketplace/app/<int:app_id>', type='http', auth='user', website=True)
    def app_detail(self, app_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        app = request.env['saas.marketplace.app'].sudo().browse(app_id).exists()
        if not app:
            return request.redirect('/my/saas/marketplace')
        eligible, reason = app.is_eligible_for_tenant(tenant)
        installed = request.env['saas.tenant.app'].sudo().search_count([
            ('tenant_id', '=', tenant.id), ('app_id', '=', app.id), ('state', '=', 'installed')])
        return request.render('saas_marketplace.portal_app_detail', {
            'tenant': tenant, 'app': app, 'eligible': eligible, 'reason': reason,
            'installed': bool(installed), 'page_name': 'saas_marketplace'})

    @http.route('/my/saas/marketplace/install', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def install(self, app_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_marketplace.services.marketplace_service import MarketplaceService
        try:
            MarketplaceService(request.env(su=True)).install_app(tenant, int(app_id))
            return request.redirect('/my/saas/marketplace/installed?status=success')
        except Exception as e:
            return request.redirect(f'/my/saas/marketplace/app/{app_id}?error={e}')

    @http.route('/my/saas/marketplace/installed', type='http', auth='user', website=True)
    def installed_apps(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        apps = request.env['saas.tenant.app'].sudo().search([
            ('tenant_id', '=', tenant.id), ('state', '!=', 'uninstalled')])
        return request.render('saas_marketplace.portal_installed_apps', {
            'tenant': tenant, 'apps': apps, 'status': kw.get('status'), 'page_name': 'saas_marketplace'})

    @http.route('/my/saas/marketplace/uninstall', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def uninstall(self, tenant_app_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        tenant_app = request.env['saas.tenant.app'].sudo().search([
            ('id', '=', int(tenant_app_id)), ('tenant_id', '=', tenant.id)], limit=1)
        if tenant_app:
            try:
                tenant_app.action_uninstall()
            except Exception as e:
                return request.redirect(f'/my/saas/marketplace/installed?error={e}')
        return request.redirect('/my/saas/marketplace/installed')
