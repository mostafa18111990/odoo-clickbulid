from odoo import http
from odoo.http import request, Response
import json


class SaasMonitoringEndpoints(http.Controller):

    @http.route('/healthz', type='http', auth='none', csrf=False, methods=['GET'])
    def healthz(self, **kw):
        return Response(json.dumps({'status': 'ok'}),
                        content_type='application/json', status=200)

    @http.route('/readyz', type='http', auth='none', csrf=False, methods=['GET'])
    def readyz(self, **kw):
        try:
            request.env.cr.execute('SELECT 1')
            request.env.cr.fetchone()
            return Response(json.dumps({'status': 'ready'}),
                            content_type='application/json', status=200)
        except Exception as e:
            return Response(json.dumps({'status': 'not_ready', 'error': str(e)}),
                            content_type='application/json', status=503)

    @http.route('/metrics', type='http', auth='none', csrf=False, methods=['GET'])
    def metrics(self, **kw):
        from odoo.addons.saas_monitoring.services.metrics_service import MetricsService
        # In production, restrict access to Prometheus scraper IP via reverse proxy.
        text = MetricsService(request.env(su=True)).prometheus_format()
        return Response(text, content_type='text/plain; version=0.0.4', status=200)
