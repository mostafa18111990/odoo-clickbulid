from . import models
from . import services
from . import controllers


def _register_event_handlers():
    """Wire SSL bridge into tenant lifecycle events."""
    from odoo.addons.saas_core.services.event_bus_service import EventBusService

    def _on_tenant_activated(env, event, payload):
        tenant_id = payload.get('tenant_id') or getattr(event, 'tenant_id', None)
        if hasattr(tenant_id, 'id'):
            tenant_id = tenant_id.id
        if not tenant_id:
            return
        tenant = env['saas.tenant'].sudo().browse(tenant_id)
        if not tenant.exists():
            return
        from odoo.addons.saas_domain_manager.services.ssl_bridge_service \
            import SslBridgeService
        ok, reason = SslBridgeService(env).request_tenant_subdomain_cert(tenant)
        import logging
        logging.getLogger(__name__).info(
            'tenant.activated cert request for %s: ok=%s reason=%s',
            tenant.subdomain, ok, reason)

    EventBusService.subscribe('tenant.activated', _on_tenant_activated)
    EventBusService.subscribe('tenant.provisioned', _on_tenant_activated)


_register_event_handlers()
