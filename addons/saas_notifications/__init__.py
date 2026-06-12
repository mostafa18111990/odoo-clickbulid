from . import models
from . import services
from . import controllers


def _register_event_handlers():
    try:
        from odoo.addons.saas_core.services.event_bus_service import EventBusService

        EVENT_TO_NOTIFICATION = {
            'tenant.lead.created': 'welcome_lead',
            'tenant.trial.started': 'trial_started',
            'tenant.trial.reminder': 'trial_reminder',
            'tenant.trial.expired': 'trial_expired',
            'tenant.activated': 'tenant_activated',
            'tenant.suspended': 'tenant_suspended',
            'tenant.grace_period.started': 'grace_period_started',
            'tenant.cancelled': 'tenant_cancelled',
            'subscription.created': 'subscription_created',
            'subscription.renewed': 'subscription_renewed',
            'subscription.upgraded': 'subscription_upgraded',
            'subscription.cancelled': 'subscription_cancelled',
            'payment.received': 'payment_received',
            'payment.failed': 'payment_failed',
            'payment.refunded': 'payment_refunded',
            'invoice.generated': 'invoice_generated',
            'invoice.paid': 'invoice_paid',
            'invoice.overdue': 'invoice_overdue',
            'domain.verified': 'domain_verified',
            'domain.ssl.issued': 'domain_ssl_issued',
            'backup.completed': 'backup_completed',
            'provisioning.completed': 'provisioning_completed',
            'provisioning.failed': 'provisioning_failed',
        }

        def _make_handler(code):
            def handler(env, event, payload):
                from odoo.addons.saas_notifications.services.notification_dispatcher import NotificationDispatcher
                NotificationDispatcher(env).dispatch(notification_code=code, event=event, payload=payload)
            handler.__name__ = f'notify_{code}'
            return handler

        for evt, code in EVENT_TO_NOTIFICATION.items():
            EventBusService.subscribe(evt, _make_handler(code))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('saas_notifications: handler reg failed: %s', e)


_register_event_handlers()
