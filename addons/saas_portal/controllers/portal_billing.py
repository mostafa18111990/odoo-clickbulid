from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain
import logging

_logger = logging.getLogger(__name__)


class SaasPortalBilling(SaasPortalMain):

    @http.route('/my/saas/invoices', type='http', auth='user', website=True)
    def saas_invoices(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        invoices = PortalService(request.env).get_invoices(tenant)
        return request.render('saas_portal.portal_invoices',
                              {'tenant': tenant, 'invoices': invoices, 'page_name': 'saas_invoices'})

    @http.route('/my/saas/invoices/<int:invoice_id>', type='http', auth='user', website=True)
    def saas_invoice_detail(self, invoice_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            invoice = PortalService(request.env).get_invoice(tenant, invoice_id)
        except Exception:
            return request.redirect('/my/saas/invoices')
        return request.render('saas_portal.portal_invoice_detail',
                              {'tenant': tenant, 'invoice': invoice, 'page_name': 'saas_invoices'})

    @http.route('/my/saas/invoices/<int:invoice_id>/pdf', type='http', auth='user', website=True)
    def saas_invoice_pdf(self, invoice_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_portal.services.portal_service import PortalService
        try:
            invoice = PortalService(request.env).get_invoice(tenant, invoice_id)
        except Exception:
            return request.redirect('/my/saas/invoices')
        if invoice.pdf_attachment_id:
            pdf_content = invoice.pdf_attachment_id.raw
        else:
            report = request.env.ref('saas_billing.action_report_saas_invoice')
            pdf_content, _ct = report.sudo()._render_qweb_pdf([invoice.id])
        return request.make_response(pdf_content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'attachment; filename=Invoice-{invoice.number}.pdf')])

    @http.route('/my/saas/payment-methods', type='http', auth='user', website=True)
    def saas_payment_methods(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        methods = request.env['saas.payment.method'].sudo().search([
            ('tenant_id', '=', tenant.id), ('is_active', '=', True)])
        return request.render('saas_portal.portal_payment_methods',
                              {'tenant': tenant, 'methods': methods, 'page_name': 'saas_payment_methods'})

    @http.route('/my/saas/payment-methods/<int:method_id>/default', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def saas_set_default_method(self, method_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        method = request.env['saas.payment.method'].sudo().search([
            ('id', '=', method_id), ('tenant_id', '=', tenant.id)], limit=1)
        if method:
            method.action_set_default()
        return request.redirect('/my/saas/payment-methods')
