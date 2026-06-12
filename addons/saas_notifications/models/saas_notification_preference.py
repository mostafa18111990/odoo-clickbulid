from odoo import models, fields, api


class SaasNotificationPreference(models.Model):
    _name = 'saas.notification.preference'
    _description = 'Notification Preference'
    _rec_name = 'tenant_id'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    billing_email = fields.Boolean(string='Billing Email', default=True)
    billing_sms = fields.Boolean(string='Billing SMS', default=True)
    subscription_email = fields.Boolean(string='Subscription Email', default=True)
    subscription_sms = fields.Boolean(string='Subscription SMS', default=False)
    lifecycle_email = fields.Boolean(string='Lifecycle Email', default=True)
    lifecycle_sms = fields.Boolean(string='Lifecycle SMS', default=False)
    technical_email = fields.Boolean(string='Technical Email', default=True)
    technical_inapp = fields.Boolean(string='Technical In-App', default=True)
    marketing_email = fields.Boolean(string='Marketing Email', default=True)
    marketing_sms = fields.Boolean(string='Marketing SMS', default=False)
    digest_mode = fields.Boolean(string='Daily Digest', default=False)

    _sql_constraints = [('tenant_unique', 'UNIQUE(tenant_id)', 'One preference set per tenant.')]

    @api.model
    def get_or_create(self, tenant):
        pref = self.search([('tenant_id', '=', tenant.id)], limit=1)
        if not pref:
            pref = self.sudo().create({'tenant_id': tenant.id})
        return pref

    def allows(self, category, channel):
        self.ensure_one()
        field = f'{category}_{channel}'
        if hasattr(self, field):
            return getattr(self, field)
        return True
