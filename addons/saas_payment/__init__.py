from . import models
from . import gateways
from . import services
from . import controllers


def _register_event_handlers():
    try:
        from odoo.addons.saas_core.services.event_bus_service import EventBusService

        def on_payment_retry_scheduled(env, event, payload):
            from odoo.addons.saas_payment.services.payment_service import PaymentService
            PaymentService(env).handle_retry_scheduled(payload)

        EventBusService.subscribe('payment.retry.scheduled', on_payment_retry_scheduled)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('saas_payment: handler reg failed: %s', e)


_register_event_handlers()
