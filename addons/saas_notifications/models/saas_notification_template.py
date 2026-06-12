from odoo import models, fields, api
import re
import logging

_logger = logging.getLogger(__name__)
CHANNELS = [('email', 'Email'), ('sms', 'SMS'), ('inapp', 'In-App')]


class SaasNotificationTemplate(models.Model):
    _name = 'saas.notification.template'
    _description = 'Notification Template'
    _order = 'notification_type_id, channel'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('notification_type_id', 'channel')
    def _compute_display_name(self):
        for rec in self:
            nt = rec.notification_type_id.name if rec.notification_type_id else '?'
            rec.display_name = f'{nt} ({rec.channel})'

    notification_type_id = fields.Many2one('saas.notification.type', string='Notification Type',
                                           required=True, ondelete='cascade', index=True)
    channel = fields.Selection(selection=CHANNELS, string='Channel', required=True)
    active = fields.Boolean(default=True)
    subject_en = fields.Char(string='Subject (EN)')
    subject_ar = fields.Char(string='Subject (AR)')
    body_en = fields.Html(string='Body (EN)', sanitize=False)
    body_ar = fields.Html(string='Body (AR)', sanitize=False)
    text_en = fields.Text(string='Text (EN)')
    text_ar = fields.Text(string='Text (AR)')
    title_en = fields.Char(string='Title (EN)')
    title_ar = fields.Char(string='Title (AR)')
    cta_url = fields.Char(string='CTA URL')
    cta_label_en = fields.Char(string='CTA Label (EN)')
    cta_label_ar = fields.Char(string='CTA Label (AR)')

    def render(self, context, lang='ar'):
        self.ensure_one()
        is_ar = lang == 'ar'

        def r(s):
            return self._substitute(s or '', context)

        if self.channel == 'email':
            return {'subject': r(self.subject_ar if is_ar else self.subject_en),
                    'body': r(self.body_ar if is_ar else self.body_en),
                    'cta_url': r(self.cta_url),
                    'cta_label': self.cta_label_ar if is_ar else self.cta_label_en}
        elif self.channel == 'sms':
            return {'text': r(self.text_ar if is_ar else self.text_en)}
        return {'title': r(self.title_ar if is_ar else self.title_en),
                'text': r(self.text_ar if is_ar else self.text_en),
                'cta_url': r(self.cta_url)}

    @staticmethod
    def _substitute(template_str, context):
        if not template_str:
            return ''

        def replacer(match):
            key = match.group(1).strip()
            value = context.get(key, '')
            return str(value) if value is not None else ''

        return re.sub(r'\{\{\s*([\w_.]+)\s*\}\}', replacer, template_str)
