import hashlib


class TokenService:
    def __init__(self, env):
        self.env = env

    def validate_token(self, header_value):
        if not header_value:
            return None
        token = header_value.strip()
        if token.lower().startswith('bearer '):
            token = token[7:].strip()
        if token.startswith('sk_'):
            token = token[3:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = self.env['saas.api.token'].sudo().search(
            [('token_hash', '=', token_hash), ('revoked', '=', False),
             ('active', '=', True)], limit=1)
        if not record:
            return None
        from odoo import fields
        now = fields.Datetime.now()
        if record.expires_at and record.expires_at < now:
            return None
        return record

    def touch(self, token_record, ip_address=None):
        from odoo import fields
        token_record.sudo().write({
            'last_used_at': fields.Datetime.now(),
            'last_used_ip': ip_address or '',
            'request_count': (token_record.request_count or 0) + 1,
        })
