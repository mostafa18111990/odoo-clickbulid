from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaasConfig(models.Model):
    _name = 'saas.config'
    _description = 'SaaS Platform Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', default='ClickBuild Platform Config', required=True)

    api_base_url = fields.Char(string='FastAPI Base URL', default='http://127.0.0.1:8000', required=True)
    api_internal_token = fields.Char(string='API Internal Token', required=True,
                                     groups='saas_tenant_manager.group_saas_admin')
    webhook_secret = fields.Char(string='Webhook HMAC Secret', required=True,
                                 groups='saas_tenant_manager.group_saas_admin')
    use_api_bridge = fields.Boolean(string='Use FastAPI Bridge for Provisioning', default=True)

    trial_days = fields.Integer(string='Trial Duration (days)', default=14, required=True)
    grace_period_days = fields.Integer(string='Grace Period (days)', default=3, required=True)
    archived_retention_days = fields.Integer(string='Archive Retention (days)', default=90, required=True)

    trial_reminder_days = fields.Char(string='Trial Reminder Days', default='7,3,1')
    notify_on_payment_fail = fields.Boolean(string='Notify on Payment Failure', default=True)
    notify_admin_on_provision = fields.Boolean(string='Notify Admin on New Tenant', default=True)
    admin_notification_email = fields.Char(string='Admin Notification Email', default='admin@clickbuild.com')

    platform_name = fields.Char(string='Platform Name', default='ClickBuild', required=True)
    platform_domain = fields.Char(string='Platform Domain', default='clickbuild.com', required=True)
    support_email = fields.Char(string='Support Email', default='support@clickbuild.com')
    from_email = fields.Char(string='Outgoing From Address', default='no-reply@clickbulid.com',
                             help='Used as the From: header on system emails (signup welcome, billing, etc).')
    company_vat = fields.Char(string='Company VAT Number')

    @api.constrains('trial_days')
    def _check_trial_days(self):
        for rec in self:
            if rec.trial_days < 1 or rec.trial_days > 365:
                raise ValidationError('Trial days must be between 1 and 365.')

    @api.constrains('grace_period_days')
    def _check_grace_days(self):
        for rec in self:
            if rec.grace_period_days < 0 or rec.grace_period_days > 30:
                raise ValidationError('Grace period must be between 0 and 30 days.')

    @api.model
    def _get_config(self):
        config = self.search([], limit=1, order='id asc')
        if not config:
            config = self.sudo().create({
                'name': 'ClickBuild Platform Config',
                'api_internal_token': 'CHANGE_ME',
                'webhook_secret': 'CHANGE_ME',
            })
        return config

    @api.model
    def get_trial_reminder_days(self):
        config = self._get_config()
        try:
            return [int(d.strip()) for d in config.trial_reminder_days.split(',') if d.strip()]
        except (ValueError, AttributeError):
            return [7, 3, 1]
