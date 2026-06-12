from odoo import fields


class ReferralService:
    def __init__(self, env):
        self.env = env

    def get_program(self):
        return self.env['saas.referral.program'].sudo().search([('active', '=', True)], limit=1)

    def create_referral(self, referrer_user, email=None):
        program = self.get_program()
        from datetime import timedelta
        expires = fields.Datetime.now() + timedelta(days=program.expiry_days if program else 90)
        return self.env['saas.referral'].sudo().create({
            'referrer_user_id': referrer_user.id,
            'referred_email': email,
            'expires_at': expires,
        })

    def resolve_code(self, code):
        return self.env['saas.referral'].sudo().search([('name', '=', code)], limit=1)

    def reward_referrer(self, referral):
        program = self.get_program()
        if not program:
            return
        referral.action_mark_rewarded(program.referrer_reward_value)
