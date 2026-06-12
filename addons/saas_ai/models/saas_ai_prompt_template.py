from odoo import models, fields


class SaasAiPromptTemplate(models.Model):
    _name = 'saas.ai.prompt.template'
    _description = 'AI Prompt Template'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    language = fields.Selection(
        selection=[('en', 'English'), ('ar', 'Arabic')],
        string='Language', default='en')
    request_type = fields.Selection(
        selection=[('chat', 'Chat'), ('completion', 'Completion'),
                   ('translation', 'Translation'), ('summary', 'Summary'),
                   ('classify', 'Classification'), ('other', 'Other')],
        string='Request Type', default='chat')
    system_message = fields.Text(string='System Message')
    body = fields.Text(string='Template Body', required=True,
                       help='Use {variable_name} placeholders')
    variables = fields.Text(string='Required Variables',
                            help='One per line, e.g. customer_name')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_lang_unique', 'UNIQUE(code, language)',
                         'Template code + language must be unique.')]
