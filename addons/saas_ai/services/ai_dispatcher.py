import logging
import time

_logger = logging.getLogger(__name__)


class AiDispatcher:
    def __init__(self, env):
        self.env = env

    def get_provider(self, code=None):
        Provider = self.env['saas.ai.provider'].sudo()
        if code:
            p = Provider.search([('code', '=', code), ('active', '=', True)], limit=1)
            if p:
                return p
        p = Provider.search([('is_default', '=', True), ('active', '=', True)], limit=1)
        if p:
            return p
        return Provider.search([('active', '=', True)], limit=1)

    def calculate_cost(self, provider, input_tokens, output_tokens):
        if not provider:
            return 0.0
        return ((provider.cost_per_1k_input_tokens * (input_tokens / 1000.0))
                + (provider.cost_per_1k_output_tokens * (output_tokens / 1000.0)))

    def dispatch(self, request_type, prompt, provider_code=None,
                 user=None, tenant=None, model=None, prompt_template=None):
        """Dispatch an AI request and log usage.

        In this build we DO NOT call external providers from inside Odoo
        directly — this method records the intent and returns a stubbed
        response. A worker/FastAPI bridge should consume saas.ai.usage
        rows in 'pending' status to perform the actual call. This keeps
        Odoo workers from blocking on long network requests."""
        t0 = time.time()
        provider = self.get_provider(provider_code)
        if not provider:
            raise ValueError('No active AI provider configured')
        usage = self.env['saas.ai.usage'].sudo().create({
            'provider_id': provider.id,
            'user_id': user.id if user else self.env.uid,
            'tenant_id': tenant.id if tenant else False,
            'request_type': request_type,
            'model': model or provider.default_model,
            'prompt_template_id': prompt_template.id if prompt_template else False,
            'status': 'success',
            'response_time_ms': int((time.time() - t0) * 1000),
        })
        return {'usage_id': usage.id, 'provider': provider.code, 'status': 'queued'}
