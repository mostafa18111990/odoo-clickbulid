from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)
VALID_GATEWAYS = {'paytabs', 'paymob', 'stripe', 'hyperpay', 'myfatoorah'}


class SaasPaymentController(http.Controller):

    @http.route('/saas/payment/<string:gateway>/webhook', type='http', auth='none',
                methods=['POST'], csrf=False)
    def payment_webhook(self, gateway, **kwargs):
        if gateway not in VALID_GATEWAYS:
            return request.make_response('Unknown gateway', status=404)
        raw_body = request.httprequest.get_data()
        headers = dict(request.httprequest.headers)
        try:
            env = request.env(su=True)
            from odoo.addons.saas_payment.services.webhook_service import WebhookService
            result = WebhookService(env).receive_webhook(gateway, headers, raw_body)
            status = 200 if result.get('status') in ('ok', 'ignored') else 400
            return request.make_response(json.dumps(result),
                                         headers={'Content-Type': 'application/json'}, status=status)
        except Exception as e:
            _logger.error('Webhook processing error (%s): %s', gateway, e)
            return request.make_response(json.dumps({'status': 'error', 'message': str(e)}),
                                         headers={'Content-Type': 'application/json'}, status=500)

    @http.route('/saas/payment/<string:gateway>/return', type='http', auth='none',
                methods=['GET'], csrf=False, website=True)
    def payment_return(self, gateway, **kwargs):
        tx_ref = kwargs.get('tx') or kwargs.get('session_id') or kwargs.get('tran_ref', '')
        if not tx_ref:
            return request.redirect('/my/saas')
        try:
            env = request.env(su=True)
            tx = env['saas.payment.transaction'].search([('reference', '=', tx_ref)], limit=1)
            if tx and tx.status == 'success':
                return request.redirect(f'/my/saas?payment=success&ref={tx_ref}')
            if tx:
                gw = env['saas.payment.gateway'].search([('code', '=', gateway), ('active', '=', True)], limit=1)
                if gw and tx.gateway_tx_ref:
                    result = gw.get_client().verify_payment(tx.gateway_tx_ref)
                    if result.get('success') and tx.status != 'success':
                        from odoo.addons.saas_payment.services.webhook_service import WebhookService
                        WebhookService(env)._handle_success(tx, gw, {
                            'amount': result.get('amount', tx.amount), 'currency': result.get('currency', tx.currency),
                            'gateway_ref': tx.gateway_tx_ref, 'success': True, 'raw': result.get('raw', {})})
                        return request.redirect(f'/my/saas?payment=success&ref={tx_ref}')
        except Exception as e:
            _logger.error('Payment return error: %s', e)
        return request.redirect(f'/my/saas?payment=pending&ref={tx_ref}')

    @http.route('/saas/payment/<string:gateway>/cancel', type='http', auth='none',
                methods=['GET'], csrf=False, website=True)
    def payment_cancel(self, gateway, **kwargs):
        tx_ref = kwargs.get('tx', '')
        try:
            env = request.env(su=True)
            tx = env['saas.payment.transaction'].search([
                ('reference', '=', tx_ref), ('status', '=', 'pending')], limit=1)
            if tx:
                tx.status = 'cancelled'
        except Exception as e:
            _logger.error('Cancel error: %s', e)
        return request.redirect('/my/saas?payment=cancelled')
