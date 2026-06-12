import logging

_logger = logging.getLogger(__name__)


class SmsChannel:
    def __init__(self, env):
        self.env = env

    def send(self, ntype, tenant, rendered, event=None):
        phone = getattr(tenant, 'phone', None)
        if not phone:
            return
        text = rendered.get('text', '')
        if not text:
            return
        notif = self.env['saas.notification'].sudo().create({
            'notification_type_id': ntype.id, 'tenant_id': tenant.id,
            'user_id': tenant.portal_user_id.id if tenant.portal_user_id else False,
            'channel': 'sms', 'recipient': phone, 'body': text, 'status': 'queued',
            'event_id': event.id if event else False})
        gateway = self.env['saas.sms.gateway'].sudo().get_for_phone(phone)
        if not gateway:
            notif.mark_failed('No active SMS gateway')
            return
        try:
            result = gateway.send_sms(phone, text)
            if result.get('success'):
                notif.mark_sent(provider_id=result.get('message_id'))
            else:
                notif.mark_failed(result.get('error', 'SMS send failed'))
        except Exception as e:
            _logger.error('SMS send failed to %s: %s', phone, e)
            notif.mark_failed(str(e))
