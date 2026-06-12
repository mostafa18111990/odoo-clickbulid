from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain
import logging

_logger = logging.getLogger(__name__)


class SaasPortalDomain(SaasPortalMain):

    @http.route('/my/saas/domains', type='http', auth='user', website=True)
    def saas_domains(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        domains = request.env['saas.domain'].sudo().search([
            ('tenant_id', '=', tenant.id), ('state', '!=', 'removed')])
        return request.render('saas_domain_manager.portal_domains', {
            'tenant': tenant, 'domains': domains,
            'can_add': tenant.can_add_custom_domain(), 'page_name': 'saas_domains'})

    @http.route('/my/saas/domains/add', type='http', auth='user',
                website=True, methods=['GET', 'POST'], csrf=True)
    def saas_domain_add(self, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        if not tenant.can_add_custom_domain():
            return request.redirect('/my/saas/subscription/plans?reason=custom_domain')
        if request.httprequest.method == 'POST':
            from odoo.addons.saas_domain_manager.services.domain_service import DomainService
            try:
                domain_rec = DomainService(request.env(su=True)).add_domain(
                    tenant, (post.get('domain') or '').lower().strip(), post.get('routing_type', 'cname'))
                domain_rec.action_start_verification()
                return request.redirect(f'/my/saas/domains/{domain_rec.id}')
            except Exception as e:
                return request.render('saas_domain_manager.portal_domain_add',
                                      {'tenant': tenant, 'error': str(e), 'page_name': 'saas_domains'})
        return request.render('saas_domain_manager.portal_domain_add', {'tenant': tenant, 'page_name': 'saas_domains'})

    @http.route('/my/saas/domains/<int:domain_id>', type='http', auth='user', website=True)
    def saas_domain_detail(self, domain_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        domain = request.env['saas.domain'].sudo().search([
            ('id', '=', domain_id), ('tenant_id', '=', tenant.id)], limit=1)
        if not domain:
            return request.redirect('/my/saas/domains')
        return request.render('saas_domain_manager.portal_domain_detail',
                              {'tenant': tenant, 'domain': domain, 'page_name': 'saas_domains'})

    @http.route('/my/saas/domains/<int:domain_id>/verify', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_domain_verify(self, domain_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        domain = request.env['saas.domain'].sudo().search([
            ('id', '=', domain_id), ('tenant_id', '=', tenant.id)], limit=1)
        if domain:
            domain.action_check_dns()
        return request.redirect(f'/my/saas/domains/{domain_id}')

    @http.route('/my/saas/domains/<int:domain_id>/remove', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def saas_domain_remove(self, domain_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        domain = request.env['saas.domain'].sudo().search([
            ('id', '=', domain_id), ('tenant_id', '=', tenant.id)], limit=1)
        if domain:
            domain.action_remove()
        return request.redirect('/my/saas/domains')
