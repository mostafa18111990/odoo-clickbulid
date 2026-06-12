from odoo import models, fields, api

NOTIFICATION_STATUS = [
    ('queued', 'Queued'), ('sent', 'Sent'), ('delivered', 'Delivered'),
    ('opened', 'Opened'), ('clicked', 'Clicked'), ('failed', 'Failed'), ('skipped', 'Skipped'),
]


class SaasNotification(models.Model):
    _name = 'saas.notification'
    _description = 'Notification'
    _order = 'create_date desc'
    _rec_name = 'subject'

    notification_type_id = fields.Many2one('saas.notification.type', string='Type', ondelete='set null', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Recipient Partner', ondelete='set null')
    user_id = fields.Many2one('res.users', string='Recipient User', ondelete='set null', index=True)
    channel = fields.Selection(
        selection=[('email', 'Email'), ('sms', 'SMS'), ('inapp', 'In-App')],
        string='Channel', required=True, index=True)
    recipient = fields.Char(string='Recipient')
    subject = fields.Char(string='Subject / Title')
    body = fields.Text(string='Body')
    cta_url = fields.Char(string='CTA URL')
    status = fields.Selection(selection=NOTIFICATION_STATUS, string='Status', default='queued',
                              required=True, index=True)
    sent_at = fields.Datetime(string='Sent At')
    delivered_at = fields.Datetime(string='Delivered At')
    opened_at = fields.Datetime(string='Opened At')
    read_inapp = fields.Boolean(string='Read', default=False, index=True)
    error_message = fields.Text(string='Error')
    retry_count = fields.Integer(string='Retries', default=0)
    provider_message_id = fields.Char(string='Provider Message ID')
    event_id = fields.Many2one('saas.event', string='Source Event', ondelete='set null')

    def mark_sent(self, provider_id=None):
        self.write({'status': 'sent', 'sent_at': fields.Datetime.now(), 'provider_message_id': provider_id})

    def mark_failed(self, error):
        self.write({'status': 'failed', 'error_message': error, 'retry_count': self.retry_count + 1})

    def mark_read(self):
        self.write({'read_inapp': True, 'status': 'opened', 'opened_at': fields.Datetime.now()})

    @api.model
    def get_unread_count(self, user_id):
        return self.search_count([('user_id', '=', user_id), ('channel', '=', 'inapp'), ('read_inapp', '=', False)])
