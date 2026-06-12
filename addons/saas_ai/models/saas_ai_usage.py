from odoo import models, fields


class SaasAiUsage(models.Model):
    _name = 'saas.ai.usage'
    _description = 'AI Usage Record'
    _order = 'create_date desc'

    provider_id = fields.Many2one('saas.ai.provider', string='Provider',
                                  required=True, ondelete='restrict', index=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='set null', index=True)
    request_type = fields.Selection(
        selection=[('chat', 'Chat'), ('completion', 'Completion'),
                   ('embedding', 'Embedding'), ('image', 'Image'),
                   ('translation', 'Translation'), ('summary', 'Summary'),
                   ('classify', 'Classification'), ('other', 'Other')],
        string='Request Type', default='chat', required=True, index=True)
    model = fields.Char(string='Model Used')
    prompt_template_id = fields.Many2one('saas.ai.prompt.template', string='Prompt Template',
                                         ondelete='set null')
    input_tokens = fields.Integer(string='Input Tokens')
    output_tokens = fields.Integer(string='Output Tokens')
    total_tokens = fields.Integer(string='Total Tokens', compute='_compute_total', store=True)
    cost = fields.Monetary(string='Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    response_time_ms = fields.Integer(string='Response Time (ms)')
    status = fields.Selection(
        selection=[('success', 'Success'), ('error', 'Error'),
                   ('rate_limited', 'Rate Limited'), ('timeout', 'Timeout')],
        string='Status', default='success', index=True)
    error_message = fields.Text(string='Error Message')

    from odoo import api

    @api.depends('input_tokens', 'output_tokens')
    def _compute_total(self):
        for r in self:
            r.total_tokens = (r.input_tokens or 0) + (r.output_tokens or 0)
