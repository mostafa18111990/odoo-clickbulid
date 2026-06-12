from odoo import models, fields


class SaasAiProvider(models.Model):
    _name = 'saas.ai.provider'
    _description = 'AI Provider Configuration'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Selection(
        selection=[('openai', 'OpenAI'), ('anthropic', 'Anthropic'),
                   ('google', 'Google Gemini'), ('azure', 'Azure OpenAI'),
                   ('local', 'Local / Self-hosted'), ('other', 'Other')],
        string='Provider', required=True)
    api_key_encrypted = fields.Char(string='API Key', help='Encrypted at rest')
    base_url = fields.Char(string='Base URL')
    default_model = fields.Char(string='Default Model')
    max_tokens = fields.Integer(string='Max Tokens', default=2048)
    temperature = fields.Float(string='Temperature', default=0.7)
    cost_per_1k_input_tokens = fields.Float(string='Cost / 1K Input Tokens', default=0.0)
    cost_per_1k_output_tokens = fields.Float(string='Cost / 1K Output Tokens', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    is_default = fields.Boolean(string='Default Provider', default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    timeout_seconds = fields.Integer(string='Timeout (s)', default=30)
    monthly_budget = fields.Monetary(string='Monthly Budget',
                                     currency_field='currency_id', default=0.0)
    notes = fields.Text(string='Notes')

    _sql_constraints = [('name_unique', 'UNIQUE(name)', 'Provider name must be unique.')]
