from odoo import models, fields, api

NOTIFICATION_CATEGORIES = [
    ('account', 'Account'), ('billing', 'Billing & Payments'),
    ('subscription', 'Subscription'), ('lifecycle', 'Lifecycle'),
    ('technical', 'Technical'), ('marketing', 'Marketing'),
]
PRIORITIES = [('critical', 'Critical'), ('high', 'High'), ('normal', 'Normal'), ('low', 'Low')]


class SaasNotificationType(models.Model):
    _name = 'saas.notification.type'
    _description = 'Notification Type'
    _order = 'category, sequence'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description')
    category = fields.Selection(selection=NOTIFICATION_CATEGORIES, string='Category', required=True, index=True)
    priority = fields.Selection(selection=PRIORITIES, string='Priority', default='normal', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    channel_email = fields.Boolean(string='Email', default=True)
    channel_sms = fields.Boolean(string='SMS', default=False)
    channel_inapp = fields.Boolean(string='In-App', default=True)
    is_critical = fields.Boolean(string='Critical (Cannot Disable)', default=False)
    template_ids = fields.One2many('saas.notification.template', 'notification_type_id', string='Templates')

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Notification type code must be unique.')]

    @api.model
    def get_by_code(self, code):
        return self.search([('code', '=', code), ('active', '=', True)], limit=1)
