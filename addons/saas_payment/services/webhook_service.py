import json
import logging

_logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, env):
        self.env = env

    def receive_webhook(self, gateway_code, headers, raw_body):
        gateway_rec = self.env['saas.payment.gateway'].search([
            ('code', '=', gateway_code), ('active', '=', True)], limit=1)
        if not gateway_rec:
            return {'status': 'error', 'message': f'Unknown gateway: {gateway_code}'}
        client = gateway_rec.get_client()
        if not client.verify_webhook(headers, raw_body):
            return {'status': 'error', 'message': 'Invalid signature'}
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            return {'status': 'error', 'message': 'Invalid JSON body'}
        parsed = client.parse_webhook(headers, body)
        event = parsed.get('event', 'unknown')
        gateway_ref = parsed.get('gateway_ref', '')
        order_id = parsed.get('order_id', '')
        if not gateway_ref and not order_id:
            return {'status': 'ignored', 'message': 'No identifiable reference'}
        if gateway_ref:
            existing = self.env['saas.payment.transaction'].search([
                ('gateway_tx_ref', '=', gateway_ref), ('status', 'in', ('success', 'refunded'))], limit=1)
            if existing:
                return {'status': 'ignored', 'message': 'Already processed'}
        tx = self._find_transaction(gateway_ref, order_id)
        if gateway_code in ('paytabs', 'hyperpay') and gateway_ref:
            try:
                verified = client.verify_payment(gateway_ref)
                parsed['success'] = verified.get('success', False)
                parsed['amount'] = verified.get('amount', parsed.get('amount', 0))
            except Exception as e:
                _logger.warning('Re-verification failed for %s: %s', gateway_ref, e)
        if event == 'payment.success' and parsed.get('success'):
            return self._handle_success(tx, gateway_rec, parsed)
        if event == 'payment.failed':
            return self._handle_failed(tx, gateway_rec, parsed)
        if event == 'refund':
            return self._handle_refund(tx, gateway_rec, parsed)
        return {'status': 'ignored', 'message': f'Unhandled event: {event}'}

    def _find_transaction(self, gateway_ref, order_id):
        TX = self.env['saas.payment.transaction']
        if gateway_ref:
            tx = TX.search([('gateway_tx_ref', '=', gateway_ref)], limit=1)
            if tx:
                return tx
        if order_id:
            tx = TX.search([('reference', '=', order_id)], limit=1)
            if tx:
                return tx
        return TX.browse()

    def _handle_success(self, tx, gateway_rec, parsed):
        amount = parsed.get('amount', 0)
        gateway_ref = parsed.get('gateway_ref', '')
        if tx.exists():
            if tx.status == 'success':
                return {'status': 'ignored', 'message': 'Already marked success'}
            tx.mark_success(gateway_response=parsed.get('raw', {}))
            if gateway_ref:
                tx.gateway_tx_ref = gateway_ref
            if tx.invoice_id:
                tx.invoice_id.action_mark_paid(amount=amount or tx.amount, tx_id=gateway_ref)
            if tx.subscription_id:
                sub = tx.subscription_id
                sub.record_payment_success(amount or tx.amount, gateway_ref)
                from odoo.addons.saas_subscription.services.renewal_service import RenewalService
                RenewalService(self.env).on_renewal_payment_success(sub, amount or tx.amount, gateway_ref)
        self.env['saas.event']._publish(event_type='payment.received',
            model='saas.payment.transaction', record_id=tx.id if tx.exists() else None,
            payload={'amount': amount, 'currency': parsed.get('currency', ''), 'gateway': gateway_rec.code,
                     'gateway_tx_id': gateway_ref,
                     'subscription_id': tx.subscription_id.id if tx.exists() and tx.subscription_id else None,
                     'invoice_id': tx.invoice_id.id if tx.exists() and tx.invoice_id else None,
                     'tenant_id': tx.tenant_id.id if tx.exists() else None},
            tenant_id=tx.tenant_id.id if tx.exists() else None)
        return {'status': 'ok', 'message': 'Payment recorded'}

    def _handle_failed(self, tx, gateway_rec, parsed):
        if tx.exists():
            tx.mark_failed(reason=parsed.get('failure_reason', 'Payment declined'),
                           gateway_response=parsed.get('raw', {}))
            if tx.subscription_id:
                from odoo.addons.saas_subscription.services.renewal_service import RenewalService
                RenewalService(self.env).on_renewal_payment_failure(tx.subscription_id,
                    parsed.get('failure_reason', 'Payment declined'))
        self.env['saas.event']._publish(event_type='payment.failed',
            payload={'gateway': gateway_rec.code, 'gateway_ref': parsed.get('gateway_ref', ''),
                     'reason': parsed.get('failure_reason', ''),
                     'tenant_id': tx.tenant_id.id if tx.exists() else None,
                     'subscription_id': tx.subscription_id.id if tx.exists() and tx.subscription_id else None},
            tenant_id=tx.tenant_id.id if tx.exists() else None)
        return {'status': 'ok', 'message': 'Failure recorded'}

    def _handle_refund(self, tx, gateway_rec, parsed):
        if tx.exists():
            tx.mark_refunded(parsed.get('amount', 0))
        self.env['saas.event']._publish(event_type='payment.refunded',
            payload={'amount': parsed.get('amount', 0), 'gateway': gateway_rec.code,
                     'invoice_id': tx.invoice_id.id if tx.exists() and tx.invoice_id else None,
                     'tenant_id': tx.tenant_id.id if tx.exists() else None},
            tenant_id=tx.tenant_id.id if tx.exists() else None)
        return {'status': 'ok', 'message': 'Refund recorded'}
