import re


class PasswordService:
    def __init__(self, env):
        self.env = env

    def get_policy(self):
        return self.env['saas.password.policy'].sudo().search(
            [('active', '=', True)], limit=1)

    def validate(self, password):
        policy = self.get_policy()
        errors = []
        if not policy:
            if len(password) < 8:
                errors.append('Password must be at least 8 characters.')
            return (len(errors) == 0, errors)
        if len(password) < policy.min_length:
            errors.append(f'Password must be at least {policy.min_length} characters.')
        if policy.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        if policy.require_lowercase and not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        if policy.require_digit and not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        if policy.require_special and not re.search(r'[^A-Za-z0-9]', password):
            errors.append('Password must contain at least one special character.')
        return (len(errors) == 0, errors)
