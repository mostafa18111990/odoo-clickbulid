from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class EmailChannel:
    def __init__(self, env):
        self.env = env

    def send(self, ntype, tenant, rendered, event=None):
        recipient = tenant.customer_email
        if not recipient:
            return
        subject = rendered.get('subject', '')
        body = rendered.get('body', '')
        cta_url = rendered.get('cta_url', '')
        cta_label = rendered.get('cta_label', '')
        html_body = self._wrap_html(body, cta_url, cta_label)
        notif = self.env['saas.notification'].sudo().create({
            'notification_type_id': ntype.id, 'tenant_id': tenant.id,
            'user_id': tenant.portal_user_id.id if tenant.portal_user_id else False,
            'channel': 'email', 'recipient': recipient, 'subject': subject, 'body': body,
            'cta_url': cta_url, 'status': 'queued', 'event_id': event.id if event else False})
        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject, 'body_html': html_body, 'email_to': recipient,
                'email_from': self._get_from_address(), 'auto_delete': False})
            mail.send()
            notif.mark_sent(provider_id=str(mail.id))
        except Exception as e:
            _logger.error('Email send failed to %s: %s', recipient, e)
            notif.mark_failed(str(e))

    def _get_from_address(self):
        # From must equal the authenticated SMTP mailbox — the provider
        # (Hostinger) rejects any other sender address (553).
        config = self.env['saas.config'].sudo()._get_config()
        server = self.env['ir.mail_server'].sudo().search([], order='sequence', limit=1)
        sender = server.smtp_user if server and server.smtp_user else f'noreply@{config.platform_domain}'
        return f'{config.platform_name} <{sender}>'

    def _wrap_html(self, body, cta_url, cta_label):
        cta_html = ''
        if cta_url and cta_label:
            cta_html = (f'<div style="text-align:center; margin:24px 0;">'
                        f'<a href="{cta_url}" style="background:#6d28d9; color:white; padding:12px 32px;'
                        f' border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block;">'
                        f'{cta_label}</a></div>')
        return ('<html><body style="margin:0; padding:0; background:#f5f3ff; font-family:Arial;">'
                '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f3ff; padding:24px 0;">'
                '<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0"'
                ' style="background:white; border-radius:12px; overflow:hidden;">'
                '<tr><td style="background:linear-gradient(135deg,#6d28d9,#9333ea); padding:24px; text-align:center;">'
                '<h1 style="color:white; margin:0; font-size:24px;">ClickBuild</h1></td></tr>'
                f'<tr><td style="padding:32px;"><div style="color:#374151; font-size:15px;">{body}</div>'
                f'{cta_html}</td></tr>'
                '<tr><td style="background:#faf5ff; padding:16px 32px; text-align:center; border-top:1px solid #e5e7eb;">'
                '<p style="color:#9ca3af; font-size:12px; margin:0;">ClickBuild · clickbuild.com</p>'
                '</td></tr></table></td></tr></table></body></html>')
