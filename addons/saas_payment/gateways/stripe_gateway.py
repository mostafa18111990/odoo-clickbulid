from .base_gateway import BaseGateway
import hmac
import hashlib
import time
import logging

_logger = logging.getLogger(__name__)


class StripeGateway(BaseGateway):
    STRIPE_BASE = 'https://api.stripe.com/v1'

    def _headers(self):
        return {'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/x-www-form-urlencoded'}

    def _post_form(self, url, data):
        import requests
        resp = requests.post(url, data=data, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url, return_url, cancel_url):
        cents = int(round(amount * 100))
        session = self._post_form(f'{self.STRIPE_BASE}/checkout/sessions', {
            'mode': 'payment', 'success_url': f'{return_url}?session_id={{CHECKOUT_SESSION_ID}}',
            'cancel_url': cancel_url, 'line_items[0][quantity]': '1',
            'line_items[0][price_data][currency]': currency.lower(),
            'line_items[0][price_data][unit_amount]': str(cents),
            'line_items[0][price_data][product_data][name]': description,
            'metadata[order_id]': order_id, 'customer_email': customer_email,
            'payment_intent_data[metadata][order_id]': order_id})
        return {'checkout_url': session.get('url', ''),
                'gateway_ref': session.get('payment_intent', session.get('id', '')),
                'order_id': order_id, 'expires_at': None, 'raw': session}

    def verify_payment(self, gateway_ref):
        import requests
        resp = requests.get(f'{self.STRIPE_BASE}/payment_intents/{gateway_ref}',
                            headers=self._headers(), timeout=30)
        resp.raise_for_status()
        pi = resp.json()
        status = pi.get('status', '')
        return {'success': status == 'succeeded', 'gateway_ref': gateway_ref,
                'amount': pi.get('amount', 0) / 100, 'currency': pi.get('currency', '').upper(),
                'status': 'success' if status == 'succeeded' else status, 'raw': pi}

    def refund(self, gateway_ref, amount, reason=''):
        rd = self._post_form(f'{self.STRIPE_BASE}/refunds', {
            'payment_intent': gateway_ref, 'amount': str(int(round(amount * 100))),
            'reason': 'requested_by_customer'})
        return {'success': rd.get('status') == 'succeeded', 'refund_ref': rd.get('id', ''),
                'amount': amount, 'raw': rd}

    def charge_stored(self, gateway_token, amount, currency, order_id, description):
        pi = self._post_form(f'{self.STRIPE_BASE}/payment_intents', {
            'amount': str(int(round(amount * 100))), 'currency': currency.lower(),
            'payment_method': gateway_token, 'confirm': 'true', 'off_session': 'true',
            'description': description, 'metadata[order_id]': order_id})
        return {'success': pi.get('status') == 'succeeded', 'gateway_ref': pi.get('id', ''),
                'amount': amount, 'currency': currency, 'raw': pi}

    def verify_webhook(self, headers, raw_body):
        sig = headers.get('stripe-signature', '')
        if not sig or not self.webhook_secret:
            return False
        try:
            parts = {k: v for k, v in (p.split('=', 1) for p in sig.split(',') if '=' in p)}
            ts, signature = parts.get('t', ''), parts.get('v1', '')
            if not ts or not signature:
                return False
            if abs(time.time() - int(ts)) > 300:
                return False
            payload = f'{ts}.{raw_body.decode("utf-8")}'
            expected = hmac.new(self.webhook_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            _logger.error('Stripe webhook verify failed: %s', e)
            return False

    def parse_webhook(self, headers, body):
        et = body.get('type', '')
        obj = body.get('data', {}).get('object', {})
        if et == 'payment_intent.succeeded':
            return {'event': 'payment.success', 'gateway_ref': obj.get('id', ''),
                    'order_id': obj.get('metadata', {}).get('order_id', ''),
                    'amount': obj.get('amount', 0) / 100, 'currency': obj.get('currency', '').upper(),
                    'status': 'success', 'raw': body}
        if et in ('payment_intent.payment_failed', 'charge.failed'):
            return {'event': 'payment.failed', 'gateway_ref': obj.get('id', ''),
                    'order_id': obj.get('metadata', {}).get('order_id', ''),
                    'amount': obj.get('amount', 0) / 100, 'currency': obj.get('currency', '').upper(),
                    'status': 'failed', 'raw': body}
        if et == 'charge.refunded':
            return {'event': 'refund', 'gateway_ref': obj.get('payment_intent', ''), 'order_id': '',
                    'amount': obj.get('amount_refunded', 0) / 100, 'currency': obj.get('currency', '').upper(),
                    'status': 'refunded', 'raw': body}
        return {'event': 'unknown', 'gateway_ref': '', 'order_id': '', 'amount': 0,
                'currency': '', 'status': 'unknown', 'raw': body}
