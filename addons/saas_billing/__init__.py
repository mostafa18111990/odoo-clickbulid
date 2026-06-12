from . import models
from . import services


def _register_event_handlers():
    try:
        from odoo.addons.saas_core.services.event_bus_service import EventBusService

        def on_payment_received(env, event, payload):
            sub_id = payload.get('subscription_id')
            tx_id = payload.get('tx_id') or payload.get('gateway_tx_id', '')
            amount = payload.get('amount', 0)
            if not sub_id:
                return
            from odoo.addons.saas_billing.services.invoice_service import InvoiceService
            InvoiceService(env).on_payment_received(sub_id, tx_id, amount)

        def on_subscription_renewed(env, event, payload):
            if payload.get('type') == 'reminder':
                return
            sub_id = payload.get('subscription_id')
            if not sub_id:
                return
            from odoo.addons.saas_billing.services.invoice_service import InvoiceService
            InvoiceService(env).generate_renewal_invoice(sub_id)

        EventBusService.subscribe('payment.received', on_payment_received)
        EventBusService.subscribe('subscription.renewed', on_subscription_renewed)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('saas_billing: handler reg failed: %s', e)


_register_event_handlers()
