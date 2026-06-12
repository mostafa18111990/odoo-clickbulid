from .base_gateway import BaseGateway
import hmac
import hashlib
import logging

_logger = logging.getLogger(__name__)
PAYMOB_BASE = 'https://accept.paymob.com/api'


class PayMobGateway(BaseGateway):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.card_integration_id = self.extra.get('card_integration_id', '')
        self.iframe_id = self.extra.get('iframe_id', '')

    def _auth(self):
        data = self._post(f'{PAYMOB_BASE}/auth/tokens', {'api_key': self.api_key})
        token = data.get('token', '')
        if not token:
            raise RuntimeError('PayMob: failed to get auth token')
        return token

    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url, return_url, cancel_url):
        cents = int(round(amount * 100))
        token = self._auth()
        order = self._post(f'{PAYMOB_BASE}/ecommerce/orders', {
            'auth_token': token, 'delivery_needed': False, 'amount_cents': cents,
            'currency': 'EGP', 'merchant_order_id': order_id, 'items': []})
        pid = order.get('id')
        if not pid:
            raise RuntimeError(f'PayMob: order failed: {order}')
        first, last = (customer_name.split(' ', 1) + [''])[:2]
        key = self._post(f'{PAYMOB_BASE}/auth/payment_keys', {
            'auth_token': token, 'amount_cents': cents, 'expiration': 3600, 'order_id': pid,
            'currency': 'EGP', 'integration_id': self.card_integration_id,
            'billing_data': {'first_name': first, 'last_name': last or 'NA', 'email': customer_email,
                'phone_number': customer_phone or '+201000000000', 'apartment': 'NA', 'floor': 'NA',
                'street': 'NA', 'building': 'NA', 'shipping_method': 'NA', 'postal_code': 'NA',
                'city': 'Cairo', 'country': 'EG', 'state': 'Cairo'}})
        pk = key.get('token', '')
        url = (f'https://accept.paymob.com/api/acceptance/iframes/{self.iframe_id}?payment_token={pk}'
               if self.iframe_id else f'https://accept.paymob.com/api/acceptance/payment_key/{pk}')
        return {'checkout_url': url, 'gateway_ref': str(pid), 'order_id': order_id,
                'expires_at': None, 'raw': {'order_id': pid, 'payment_key': pk}}

    def verify_payment(self, gateway_ref):
        token = self._auth()
        data = self._get(f'{PAYMOB_BASE}/ecommerce/orders/{gateway_ref}',
                         headers={'Authorization': f'Bearer {token}'})
        paid = data.get('paid_amount_cents', 0) > 0
        return {'success': paid, 'gateway_ref': gateway_ref, 'amount': data.get('amount_cents', 0) / 100,
                'currency': data.get('currency', 'EGP'), 'status': 'success' if paid else 'pending', 'raw': data}

    def refund(self, gateway_ref, amount, reason=''):
        token = self._auth()
        data = self._post(f'{PAYMOB_BASE}/acceptance/void_refund/refund',
                          {'auth_token': token, 'transaction_id': gateway_ref,
                           'amount_cents': int(round(amount * 100))})
        return {'success': data.get('success', False), 'refund_ref': str(data.get('id', '')),
                'amount': amount, 'raw': data}

    def verify_webhook(self, headers, raw_body):
        if not self.webhook_secret:
            return False
        try:
            import json
            obj = json.loads(raw_body).get('obj', {})
            concat = (str(obj.get('amount_cents', '')) + str(obj.get('created_at', '')) +
                      str(obj.get('currency', '')) + str(obj.get('error_occured', '')) +
                      str(obj.get('has_parent_transaction', '')) + str(obj.get('id', '')) +
                      str(obj.get('integration_id', '')) + str(obj.get('is_3d_secure', '')) +
                      str(obj.get('is_auth', '')) + str(obj.get('is_capture', '')) +
                      str(obj.get('is_refunded', '')) + str(obj.get('is_standalone_payment', '')) +
                      str(obj.get('is_voided', '')) + str(obj.get('order', {}).get('id', '')) +
                      str(obj.get('owner', '')) + str(obj.get('pending', '')) +
                      str(obj.get('source_data', {}).get('pan', '')) +
                      str(obj.get('source_data', {}).get('sub_type', '')) +
                      str(obj.get('source_data', {}).get('type', '')) + str(obj.get('success', '')))
            expected = hmac.new(self.webhook_secret.encode(), concat.encode(), hashlib.sha512).hexdigest()
            incoming = headers.get('hmac', '') or json.loads(raw_body).get('hmac', '')
            return hmac.compare_digest(expected.lower(), incoming.lower())
        except Exception as e:
            _logger.error('PayMob webhook verify failed: %s', e)
            return False

    def parse_webhook(self, headers, body):
        obj = body.get('obj', {})
        success = obj.get('success', False)
        return {'event': 'payment.success' if success else 'payment.failed',
                'gateway_ref': str(obj.get('order', {}).get('id', '')),
                'order_id': str(obj.get('order', {}).get('merchant_order_id', '')),
                'amount': obj.get('amount_cents', 0) / 100, 'currency': obj.get('currency', 'EGP'),
                'status': 'success' if success else 'failed', 'raw': body}
