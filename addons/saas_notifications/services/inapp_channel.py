from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class InAppChannel:
    def __init__(self, env):
        self.env = env

    def send(self, ntype, tenant, rendered, event=None):
        if not tenant.portal_user_id:
            return
        self.env['saas.notification'].sudo().create({
            'notification_type_id': ntype.id, 'tenant_id': tenant.id,
            'user_id': tenant.portal_user_id.id, 'channel': 'inapp',
            'subject': rendered.get('title', ''), 'body': rendered.get('text', ''),
            'cta_url': rendered.get('cta_url', ''), 'status': 'sent',
            'sent_at': fields.Datetime.now(), 'read_inapp': False,
            'event_id': event.id if event else False})
