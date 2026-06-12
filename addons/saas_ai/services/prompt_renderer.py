class PromptRenderer:
    def __init__(self, env):
        self.env = env

    def render(self, code, language='en', variables=None):
        template = self.env['saas.ai.prompt.template'].sudo().search(
            [('code', '=', code), ('language', '=', language),
             ('active', '=', True)], limit=1)
        if not template:
            template = self.env['saas.ai.prompt.template'].sudo().search(
                [('code', '=', code), ('active', '=', True)], limit=1)
        if not template:
            raise ValueError(f'Prompt template {code} not found')
        body = template.body
        for k, v in (variables or {}).items():
            body = body.replace('{' + k + '}', str(v))
        return {
            'system': template.system_message or '',
            'body': body,
            'template_id': template.id,
        }
