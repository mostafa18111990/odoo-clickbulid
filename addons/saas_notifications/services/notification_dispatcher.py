from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_notifications.services.email_channel import EmailChannel
        from odoo.addons.saas_notifications.services.sms_channel import SmsChannel
        from odoo.addons.saas_notifications.services.inapp_channel import InAppChannel
        self.channels = {'email': EmailChannel(env), 'sms': SmsChannel(env), 'inapp': InAppChannel(env)}

    def dispatch(self, notification_code, event=None, payload=None):
        payload = payload or {}
        ntype = self.env['saas.notification.type'].get_by_code(notification_code)
        if not ntype:
            _logger.debug('No notification type for: %s', notification_code)
            return
        tenant = self._resolve_tenant(payload)
        if not tenant:
            return
        context = self._build_context(tenant, payload)
        lang = self._resolve_language(tenant)
        for channel_name in self._resolve_channels(ntype, tenant):
            try:
                self._send_via_channel(channel_name, ntype, tenant, context, lang, event)
            except Exception as e:
                _logger.error('Dispatch failed (%s/%s): %s', notification_code, channel_name, e)

    def _resolve_tenant(self, payload):
        tenant_id = payload.get('tenant_id')
        if tenant_id:
            return self.env['saas.tenant'].sudo().browse(int(tenant_id)).exists()
        if payload.get('subscription_id'):
            sub = self.env['saas.subscription'].sudo().browse(int(payload['subscription_id'])).exists()
            if sub:
                return sub.tenant_id
        if payload.get('invoice_id'):
            inv = self.env['saas.invoice'].sudo().browse(int(payload['invoice_id'])).exists()
            if inv:
                return inv.tenant_id
        return None

    def _resolve_language(self, tenant):
        if tenant.portal_user_id and tenant.portal_user_id.lang:
            return 'ar' if tenant.portal_user_id.lang.startswith('ar') else 'en'
        return 'ar'

    def _resolve_channels(self, ntype, tenant):
        defaults = {'email': ntype.channel_email, 'sms': ntype.channel_sms, 'inapp': ntype.channel_inapp}
        if ntype.is_critical:
            return [c for c, enabled in defaults.items() if enabled]
        pref = self.env['saas.notification.preference'].sudo().get_or_create(tenant)
        return [c for c, enabled in defaults.items() if enabled and pref.allows(ntype.category, c)]

    def _build_context(self, tenant, payload):
        config = self.env['saas.config'].sudo()._get_config()
        context = {
            'tenant_name': tenant.name, 'customer_name': tenant.customer_name or tenant.name,
            'subdomain': tenant.subdomain,
            'tenant_url': tenant.get_sso_url() if hasattr(tenant, 'get_sso_url') else '',
            'plan_name': tenant.plan_id.name if tenant.plan_id else '',
            'platform_name': config.platform_name, 'platform_domain': config.platform_domain,
            'support_email': config.support_email,
            'portal_url': f'https://{config.platform_domain}/my/saas',
        }
        context.update({k: v for k, v in payload.items() if not isinstance(v, (dict, list))})
        return context

    def _send_via_channel(self, channel_name, ntype, tenant, context, lang, event):
        template = self.env['saas.notification.template'].sudo().search([
            ('notification_type_id', '=', ntype.id), ('channel', '=', channel_name),
            ('active', '=', True)], limit=1)
        if not template:
            return
        rendered = template.render(context, lang)
        channel = self.channels.get(channel_name)
        if channel:
            channel.send(ntype=ntype, tenant=tenant, rendered=rendered, event=event)
