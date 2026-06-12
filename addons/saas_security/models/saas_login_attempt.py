from odoo import models, fields, api
from datetime import timedelta


class SaasLoginAttempt(models.Model):
    _name = 'saas.login.attempt'
    _description = 'Login Attempt Audit'
    _order = 'create_date desc'

    email = fields.Char(string='Email', index=True)
    user_id = fields.Many2one('res.users', string='User',
                              ondelete='set null', index=True)
    success = fields.Boolean(string='Success', index=True)
    ip_address = fields.Char(string='IP', index=True)
    user_agent = fields.Char(string='User Agent')
    failure_reason = fields.Char(string='Failure Reason')
    country = fields.Char(string='Country')

    @api.model
    def cron_cleanup_old(self):
        cutoff = fields.Datetime.now() - timedelta(days=90)
        self.search([('create_date', '<', cutoff)]).unlink()

    @api.model
    def cron_detect_brute_force(self):
        from odoo.addons.saas_security.services.brute_force_service import BruteForceService
        BruteForceService(self.env).detect_and_log()
