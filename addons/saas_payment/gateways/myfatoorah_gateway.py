from .base_gateway import BaseGateway
import hmac
import logging

_logger = logging.getLogger(__name__)
BASE = 'https://api.myfatoorah.com'
TEST = 'https://apitest.myfatoorah.com'


class MyFatoorahGateway(BaseGateway):
    def _base_url(self):
        return TEST if self.is_sandbox else BASE

    def _headers(self):
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url, return_url, cancel_url):
        data = self._post(f'{self._base_url()}/v2/SendPayment', {
            'SendInvoiceTo': customer_email, 'InvoiceValue': amount, 'CustomerName': customer_name,
            'CustomerEmail': customer_email, 'CustomerMobile': customer_phone or '',
            'MobileCountryCode': '+965', 'CallBackUrl': callback_url, 'ErrorUrl': cancel_url,
            'Language': 'AR', 'CustomerReference': order_id, 'InvoiceNote': description,
            'DisplayCurrencyIso': currency}, self._headers())
        inv = data.get('Data', {})
        return {'checkout_url': inv.get('InvoiceURL', ''), 'gateway_ref': str(inv.get('InvoiceId', '')),
                'order_id': order_id, 'expires_at': None, 'raw': data}

    def verify_payment(self, gateway_ref):
        data = self._post(f'{self._base_url()}/v2/GetPaymentStatus',
                          {'Key': gateway_ref, 'KeyType': 'InvoiceId'}, self._headers())
        inv = data.get('Data', {})
        status = inv.get('InvoiceStatus', '')
        return {'success': status == 'Paid', 'gateway_ref': gateway_ref, 'amount': inv.get('InvoiceValue', 0),
                'currency': inv.get('CurrencyIso', ''), 'status': 'success' if status == 'Paid' else 'pending',
                'raw': data}

    def refund(self, gateway_ref, amount, reason=''):
        data = self._post(f'{self._base_url()}/v2/MakeRefund', {
            'KeyType': 'InvoiceId', 'Key': gateway_ref, 'RefundChargeOnCustomer': False,
            'ServiceChargOnCustomer': False, 'Amount': amount, 'Comment': reason or 'Refund',
            'AmountDeductedFromSupplier': 0}, self._headers())
        return {'success': data.get('IsSuccess', False),
                'refund_ref': str(data.get('Data', {}).get('RefundId', '')), 'amount': amount, 'raw': data}

    def verify_webhook(self, headers, raw_body):
        if not self.webhook_secret:
            return True
        try:
            import json
            received = json.loads(raw_body).get('SecretKey', '')
            return hmac.compare_digest(received, self.webhook_secret)
        except Exception as e:
            _logger.error('MyFatoorah webhook verify failed: %s', e)
            return False

    def parse_webhook(self, headers, body):
        inv = body.get('Data', body)
        status = inv.get('InvoiceStatus', '')
        return {'event': 'payment.success' if status == 'Paid' else 'payment.failed',
                'gateway_ref': str(inv.get('InvoiceId', '')), 'order_id': str(inv.get('CustomerReference', '')),
                'amount': inv.get('InvoiceValue', 0), 'currency': inv.get('CurrencyIso', 'KWD'),
                'status': 'success' if status == 'Paid' else 'failed', 'raw': body}
