from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    demo_telegram_enabled = fields.Boolean(
        string='Enable Telegram Demo Notifications',
        config_parameter='saas_demo.telegram_enabled')
    demo_telegram_bot_token = fields.Char(
        string='Telegram Bot Token',
        config_parameter='saas_demo.telegram_bot_token')
    demo_telegram_chat_id = fields.Char(
        string='Telegram Admin Chat ID',
        config_parameter='saas_demo.telegram_chat_id')
    demo_telegram_allowed_user_ids = fields.Char(
        string='Authorized Telegram User IDs',
        config_parameter='saas_demo.telegram_allowed_user_ids',
        help='Comma-separated numeric Telegram user IDs allowed to approve or reject requests.')
    demo_telegram_webhook_secret = fields.Char(
        string='Telegram Webhook Secret',
        config_parameter='saas_demo.telegram_webhook_secret')
    demo_callback_signing_secret = fields.Char(
        string='Callback Signing Secret',
        config_parameter='saas_demo.callback_signing_secret')
    demo_whatsapp_enabled = fields.Boolean(
        string='Send Demo Credentials by WhatsApp',
        config_parameter='saas_demo.whatsapp_enabled')
    demo_whatsapp_access_token = fields.Char(
        string='WhatsApp System User Access Token',
        config_parameter='saas_demo.whatsapp_access_token')
    demo_whatsapp_phone_number_id = fields.Char(
        string='WhatsApp Phone Number ID',
        config_parameter='saas_demo.whatsapp_phone_number_id')
    demo_whatsapp_api_version = fields.Char(
        string='Meta Graph API Version', default='v23.0',
        config_parameter='saas_demo.whatsapp_api_version')
    demo_whatsapp_template_name = fields.Char(
        string='Approved WhatsApp Template',
        default='clickbuild_demo_ready_ar',
        config_parameter='saas_demo.whatsapp_template_name')
    demo_whatsapp_template_language = fields.Char(
        string='WhatsApp Template Language', default='ar',
        config_parameter='saas_demo.whatsapp_template_language')
    demo_provision_enabled = fields.Boolean(
        string='Allow Enterprise Demo Provisioning',
        config_parameter='saas_demo.provision_enabled',
        help='Keep disabled until the Enterprise provisioner and warm pool pass health checks.')
    demo_default_duration_days = fields.Integer(
        string='Default Demo Duration', default=14,
        config_parameter='saas_demo.default_duration_days')
    demo_max_requests_per_15_minutes = fields.Integer(
        string='Request Limit per 15 Minutes', default=3,
        config_parameter='saas_demo.max_requests_per_15_minutes')
