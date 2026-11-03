import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


ENV_NAME_RE = re.compile(r'^[A-Z][A-Z0-9_]{2,127}$')


class SaasAiSocialChannel(models.Model):
    _name = 'saas.ai.social.channel'
    _description = 'AI Social Channel'
    _inherit = ['mail.thread']
    _order = 'platform, name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    platform = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('tiktok', 'TikTok'),
        ('linkedin', 'LinkedIn'),
        ('x', 'X'),
        ('youtube', 'YouTube'),
        ('telegram', 'Telegram'),
    ], required=True, tracking=True, index=True)
    account_name = fields.Char(required=True)
    account_id = fields.Char(
        required=True,
        help='Platform account/page/organization identifier. Never put a token here.')
    credential_env_var = fields.Char(
        required=True,
        help='Name of the runtime environment variable containing the credential. '
             'The secret itself is never stored in Odoo.')
    webhook_secret_env_var = fields.Char(
        help='Optional environment-variable name containing the webhook secret.')
    state = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='disconnected', required=True, readonly=True, tracking=True)
    can_publish = fields.Boolean(default=True)
    can_reply = fields.Boolean(default=True)
    can_receive_messages = fields.Boolean(default=True)
    can_read_analytics = fields.Boolean(default=True)
    last_sync_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _account_unique = models.Constraint(
        'UNIQUE(company_id, platform, account_id)',
        'This social account is already configured for the company.',
    )

    @api.constrains('credential_env_var', 'webhook_secret_env_var')
    def _check_env_var_names(self):
        for channel in self:
            for value in (channel.credential_env_var, channel.webhook_secret_env_var):
                if value and not ENV_NAME_RE.fullmatch(value):
                    raise ValidationError(
                        'Credential references must be uppercase environment-variable names.')

    def action_reset_connection(self):
        self.write({'state': 'disconnected', 'last_error': False})
