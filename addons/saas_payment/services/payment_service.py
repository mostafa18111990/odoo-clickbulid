from odoo import fields
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, env):
        self.env = env

    def initiate_checkout(self, tenant, amount, currency, invoice_id=None, subscription_id=None,
                          tx_type='checkout', payment_method_id=None):
        if amount <= 0:
            raise UserError('Payment amount must be positive.')
        gateway_rec = self.env['saas.payment.gateway'].get_for_tenant(tenant, currency)
        if not gateway_rec:
            raise UserError('No active payment gateway configured for this region.')
        order_id = self.env['ir.sequence'].next_by_code('saas.payment.tx') or 'TX-MANUAL'
        tx = self.env['saas.payment.transaction'].create({
            'reference': order_id, 'tx_type': tx_type, 'status': 'pending', 'tenant_id': tenant.id,
            'gateway_id': gateway_rec.id, 'invoice_id': invoice_id, 'subscription_id': subscription_id,
            'amount': amount, 'currency': currency, 'initiated_at': fields.Datetime.now(),
            'expires_at': fields.Datetime.now() + timedelta(hours=1)})
        client = gateway_rec.get_client()
        config = self.env['saas.config']._get_config()
        base = f'https://{config.platform_domain}'
        try:
            result = client.create_payment(
                amount=amount, currency=currency, order_id=order_id,
                description=f'ClickBuild subscription - {tenant.subdomain}',
                customer_name=tenant.customer_name or tenant.name, customer_email=tenant.customer_email or '',
                customer_phone=getattr(tenant, 'phone', '') or '',
                country_code=getattr(tenant, 'customer_country', 'SA') or 'SA',
                callback_url=f'{base}/saas/payment/{gateway_rec.code}/webhook',
                return_url=f'{base}/saas/payment/{gateway_rec.code}/return?tx={order_id}',
                cancel_url=f'{base}/saas/payment/{gateway_rec.code}/cancel?tx={order_id}')
            tx.write({'gateway_tx_ref': result.get('gateway_ref', ''),
                      'gateway_order_id': result.get('gateway_ref', ''),
                      'checkout_url': result.get('checkout_url', '')})
            return {'checkout_url': result.get('checkout_url', ''), 'transaction_id': tx.id,
                    'gateway_ref': result.get('gateway_ref', ''), 'expires_at': str(result.get('expires_at', ''))}
        except Exception as e:
            tx.mark_failed(str(e))
            _logger.error('Payment initiation failed for %s: %s', tenant.subdomain, e)
            raise

    def handle_retry_scheduled(self, payload):
        tenant_id = payload.get('tenant_id')
        sub_id = payload.get('subscription_id')
        amount = payload.get('amount', 0)
        currency = payload.get('currency', 'SAR')
        if not tenant_id or amount <= 0:
            return
        tenant = self.env['saas.tenant'].browse(tenant_id).exists()
        if not tenant:
            return
        pm = self.env['saas.payment.method'].search([
            ('tenant_id', '=', tenant.id), ('is_default', '=', True),
            ('is_active', '=', True), ('verified', '=', True)], limit=1)
        if not pm:
            _logger.info('No stored payment method for %s - manual payment required', tenant.subdomain)
            return
        try:
            self._charge_stored(pm, amount, currency, sub_id)
        except Exception as e:
            _logger.error('Stored card charge failed for %s: %s', tenant.subdomain, e)
            from odoo.addons.saas_core.services.event_bus_service import EventBusService
            EventBusService(self.env).publish('payment.failed', payload={'tenant_id': tenant.id,
                'amount': amount, 'error': str(e), 'gateway': pm.gateway_id.code if pm.gateway_id else '',
                'subscription_id': sub_id}, tenant_id=tenant.id)

    def _charge_stored(self, pm, amount, currency, sub_id=None):
        gateway_rec = pm.gateway_id
        client = gateway_rec.get_client()
        seq = self.env['ir.sequence'].next_by_code('saas.payment.tx') or 'RETRY-TX'
        tx = self.env['saas.payment.transaction'].create({
            'reference': seq, 'tx_type': 'retry', 'status': 'processing', 'tenant_id': pm.tenant_id.id,
            'gateway_id': gateway_rec.id, 'subscription_id': sub_id, 'payment_method_id': pm.id,
            'amount': amount, 'currency': currency})
        result = client.charge_stored(gateway_token=pm.gateway_token, amount=amount, currency=currency,
                                      order_id=seq, description=f'Renewal - {pm.tenant_id.subdomain}')
        if result.get('success'):
            tx.mark_success(result)
            pm.verified = True
            from odoo.addons.saas_core.services.event_bus_service import EventBusService
            EventBusService(self.env).publish('payment.received', payload={'amount': amount,
                'currency': currency, 'gateway': gateway_rec.code, 'gateway_tx_id': result.get('gateway_ref', ''),
                'subscription_id': sub_id, 'tenant_id': pm.tenant_id.id}, tenant_id=pm.tenant_id.id)
        else:
            tx.mark_failed('Stored card charge failed')
            raise RuntimeError('Stored card charge failed')

    def initiate_refund(self, transaction_id, amount, reason=''):
        tx = self.env['saas.payment.transaction'].browse(transaction_id).exists()
        if not tx:
            raise UserError(f'Transaction {transaction_id} not found.')
        if tx.status != 'success':
            raise UserError('Only successful transactions can be refunded.')
        result = tx.gateway_id.get_client().refund(tx.gateway_tx_ref, amount, reason)
        if result.get('success'):
            tx.mark_refunded(amount)
            from odoo.addons.saas_core.services.event_bus_service import EventBusService
            EventBusService(self.env).publish('payment.refunded', payload={'amount': amount,
                'gateway': tx.gateway_id.code, 'invoice_id': tx.invoice_id.id if tx.invoice_id else None,
                'tenant_id': tx.tenant_id.id}, tenant_id=tx.tenant_id.id)
        return result
