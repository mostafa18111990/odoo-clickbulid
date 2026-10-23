import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class SaasController(http.Controller):

    @http.route('/saas/health', auth='none', type='http', methods=['GET'])
    def health_check(self, **kwargs):
        return Response('OK', status=200, content_type='text/plain')

    @http.route('/saas/suspended', auth='none', type='http', methods=['GET'])
    def suspended_page(self, **kwargs):
        """Shown when a tenant is suspended."""
        return request.render('saas_tenant_manager.page_suspended', {})
