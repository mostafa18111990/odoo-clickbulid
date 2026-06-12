from .base_gateway import BaseGateway
import logging

_logger = logging.getLogger(__name__)

REGION_URLS = {
    'EGY': 'https://secure-egypt.paytabs.com', 'SAU': 'https://secure.paytabs.sa',
    'ARE': 'https://secure.paytabs.com', 'KWT': 'https://secure-kuwait.paytabs.com',
    'OMN': 'https://secure-oman.paytabs.com', 'JOR': 'https://secure-jordan.paytabs.com',
    'BHR': 'https://secure-bahrain.paytabs.com', 'QAT': 'https://secure-qatar.paytabs.com',
}
COUNTRY_REGION = {'EG': 'EGY', 'SA': 'SAU', 'AE': 'ARE', 'KW': 'KWT', 'OM': 'OMN',
                  'JO': 'JOR', 'BH': 'BHR', 'QA': 'QAT'}
STATUS_MAP = {'A': 'success', 'D': 'failed', 'E': 'failed', 'V': 'cancelled', 'H': 'pending'}


class PayTabsGateway(BaseGateway):
    def _base_url(self, country_code='SA'):
        region = COUNTRY_REGION.get(country_code[:2].upper(), 'SAU')
        return REGION_URLS.get(region, REGION_URLS['SAU'])

    def _headers(self):
        return {'Authorization': self.api_key, 'Content-Type': 'application/json'}

    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url, return_url, cancel_url):
        base = 'https://secure.paytabs.sa' if self.is_sandbox else self._base_url(country_code)
        cust = {'name': customer_name, 'email': customer_email, 'phone': customer_phone or '+966500000000',
                'street1': 'N/A', 'city': 'N/A', 'state': 'N/A', 'country': country_code[:2].upper(), 'zip': '00000'}
        data = self._post(f'{base}/payment/request', {
            'profile_id': self.profile_id, 'tran_type': 'sale', 'tran_class': 'ecom',
            'cart_id': order_id, 'cart_description': description, 'cart_currency': currency,
            'cart_amount': amount, 'callback': callback_url, 'return': return_url,
            'hide_shipping': True, 'framed': False, 'lang': 'ar',
            'customer_details': cust, 'shipping_details': cust}, self._headers())
        return {'checkout_url': data.get('redirect_url', ''), 'gateway_ref': data.get('tran_ref', ''),
                'order_id': order_id, 'expires_at': None, 'raw': data}

    def verify_payment(self, gateway_ref):
        data = self._post(f'{self._base_url()}/payment/query',
                          {'profile_id': self.profile_id, 'tran_ref': gateway_ref}, self._headers())
        status_code = data.get('payment_result', {}).get('response_status', 'E')
        return {'success': status_code == 'A', 'gateway_ref': gateway_ref, 'amount': data.get('cart_amount', 0),
                'currency': data.get('cart_currency', ''), 'status': STATUS_MAP.get(status_code, 'failed'), 'raw': data}

    def refund(self, gateway_ref, amount, reason=''):
        data = self._post(f'{self._base_url()}/payment/request', {
            'profile_id': self.profile_id, 'tran_type': 'refund', 'tran_class': 'ecom',
            'cart_id': f'REFUND-{gateway_ref}', 'cart_currency': 'SAR', 'cart_amount': amount,
            'cart_description': reason or 'Refund', 'tran_ref': gateway_ref}, self._headers())
        return {'success': data.get('payment_result', {}).get('response_status') == 'A',
                'refund_ref': data.get('tran_ref', ''), 'amount': amount, 'raw': data}

    def verify_webhook(self, headers, raw_body):
        return True  # PayTabs: verify via re-query in WebhookService

    def parse_webhook(self, headers, body):
        status_code = body.get('payment_result', {}).get('response_status', 'E')
        return {'event': 'payment.success' if status_code == 'A' else 'payment.failed',
                'gateway_ref': body.get('tran_ref', ''), 'order_id': body.get('cart_id', ''),
                'amount': body.get('cart_amount', 0), 'currency': body.get('cart_currency', ''),
                'status': STATUS_MAP.get(status_code, 'failed'), 'raw': body}
