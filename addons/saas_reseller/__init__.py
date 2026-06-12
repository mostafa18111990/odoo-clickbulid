from . import models
from . import services
from . import controllers


def _register_event_handlers():
    try:
        from odoo.addons.saas_core.services.event_bus_service import EventBusService

        def on_payment_received(env, event, payload):
            from odoo.addons.saas_reseller.services.commission_service import CommissionService
            CommissionService(env).accrue_commission(payload)

        EventBusService.subscribe('payment.received', on_payment_received)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('saas_reseller: handler reg failed: %s', e)


_register_event_handlers()
