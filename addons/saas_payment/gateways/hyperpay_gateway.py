from .base_gateway import BaseGateway
import logging

_logger = logging.getLogger(__name__)
LIVE = 'https://eu-prod.oppwa.com'
TEST = 'https://eu-test.oppwa.com'


class HyperPayGateway(BaseGateway):
    def _base_url(self):
        return TEST if self.is_sandbox else LIVE

    def _headers(self):
        return {'Authorization': f'Bearer {self.api_key}'}

    def _entity_id(self, method='card'):
        if method == 'mada':
            return self.extra.get('entity_id_mada') or self.profile_id
        if method == 'apple_pay':
            return self.extra.get('entity_id_applepay') or self.profile_id
        return self.extra.get('entity_id_visa_mc') or self.profile_id

    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url, return_url, cancel_url):
        import requests
        data = {'entityId': self._entity_id(), 'amount': f'{amount:.2f}', 'currency': currency,
                'paymentType': 'DB', 'merchantTransactionId': order_id, 'customer.email': customer_email,
                'customer.givenName': customer_name.split()[0] if customer_name else 'Customer',
                'customer.surname': ' '.join(customer_name.split()[1:]) or 'NA',
                'shopperResultUrl': return_url}
        resp = requests.post(f'{self._base_url()}/v1/checkouts', data=data, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()
        cid = result.get('id', '')
        return {'checkout_url': f'{self._base_url()}/paymentWidgets.js?checkoutId={cid}',
                'gateway_ref': cid, 'order_id': order_id, 'expires_at': None, 'raw': result}

    def verify_payment(self, gateway_ref):
        import requests
        resp = requests.get(f'{self._base_url()}/v1/checkouts/{gateway_ref}/payment',
                            params={'entityId': self._entity_id()}, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        code = data.get('result', {}).get('code', '')
        success = code.startswith('000.000.') or code.startswith('000.100.1')
        return {'success': success, 'gateway_ref': gateway_ref, 'amount': float(data.get('amount', 0)),
                'currency': data.get('currency', ''), 'status': 'success' if success else 'failed', 'raw': data}

    def refund(self, gateway_ref, amount, reason=''):
        import requests
        resp = requests.post(f'{self._base_url()}/v1/payments/{gateway_ref}',
                             data={'entityId': self._entity_id(), 'amount': f'{amount:.2f}',
                                   'currency': 'SAR', 'paymentType': 'RF'},
                             headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return {'success': result.get('result', {}).get('code', '').startswith('000.'),
                'refund_ref': result.get('id', ''), 'amount': amount, 'raw': result}

    def verify_webhook(self, headers, raw_body):
        return True

    def parse_webhook(self, headers, body):
        code = body.get('result', {}).get('code', '')
        success = code.startswith('000.000.') or code.startswith('000.100.1')
        return {'event': 'payment.success' if success else 'payment.failed',
                'gateway_ref': body.get('id', ''), 'order_id': body.get('merchantTransactionId', ''),
                'amount': float(body.get('amount', 0)), 'currency': body.get('currency', ''),
                'status': 'success' if success else 'failed', 'raw': body}
