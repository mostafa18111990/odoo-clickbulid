from datetime import timedelta


class RateLimitService:
    def __init__(self, env):
        self.env = env

    def check(self, token_record):
        if not token_record:
            return True
        from odoo import fields
        limit = token_record.rate_limit_per_minute or 60
        cutoff = fields.Datetime.now() - timedelta(minutes=1)
        recent = self.env['saas.api.request.log'].sudo().search_count([
            ('token_id', '=', token_record.id),
            ('create_date', '>=', cutoff)])
        return recent < limit
