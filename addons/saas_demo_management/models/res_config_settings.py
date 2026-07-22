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
