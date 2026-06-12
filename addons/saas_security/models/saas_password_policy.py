from odoo import models, fields


class SaasPasswordPolicy(models.Model):
    _name = 'saas.password.policy'
    _description = 'Password Policy'

    name = fields.Char(string='Name', required=True, default='Default Policy')
    active = fields.Boolean(default=True)
    min_length = fields.Integer(string='Minimum Length', default=10)
    require_uppercase = fields.Boolean(string='Require Uppercase', default=True)
    require_lowercase = fields.Boolean(string='Require Lowercase', default=True)
    require_digit = fields.Boolean(string='Require Digit', default=True)
    require_special = fields.Boolean(string='Require Special', default=True)
    history_count = fields.Integer(string='Password History Count', default=5)
    rotation_days = fields.Integer(string='Force Rotation (days)', default=180,
                                   help='0 = no forced rotation')
    max_failed_attempts = fields.Integer(string='Max Failed Attempts', default=5)
    lockout_minutes = fields.Integer(string='Lockout Duration (minutes)', default=30)
    breach_check_enabled = fields.Boolean(string='HaveIBeenPwned Check', default=False)
