from odoo import models, fields, api

ATTEMPT_STATES = [
    ('scheduled', 'Scheduled'), ('pending', 'Pending Execution'),
    ('executed', 'Executed'), ('skipped', 'Skipped'), ('failed', 'Failed'),
]
ATTEMPT_RESULTS = [
    ('payment_success', 'Payment Succeeded'), ('payment_failed', 'Payment Failed'),
    ('email_sent', 'Email Sent'), ('suspended', 'Tenant Suspended'),
    ('cancelled', 'Tenant Cancelled'), ('skipped', 'Skipped (state changed)'),
    ('error', 'System Error'),
]


class SaasDunningAttempt(models.Model):
    _name = 'saas.dunning.attempt'
    _description = 'SaaS Dunning Attempt'
    _order = 'scheduled_at asc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)

    @api.depends('tenant_id', 'rule_id', 'attempt_number')
    def _compute_display_name(self):
        for rec in self:
            t = rec.tenant_id.subdomain if rec.tenant_id else '?'
            r = rec.rule_id.name if rec.rule_id else '?'
            rec.display_name = f'{t} - {r} (#{rec.attempt_number})'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    rule_id = fields.Many2one('saas.dunning.rule', string='Rule', required=True, ondelete='cascade')
    attempt_number = fields.Integer(string='Attempt #', default=1)
    scheduled_at = fields.Datetime(string='Scheduled At', required=True, index=True)
    executed_at = fields.Datetime(string='Executed At', readonly=True)
    state = fields.Selection(selection=ATTEMPT_STATES, string='State', default='scheduled', required=True, index=True)
    result = fields.Selection(selection=ATTEMPT_RESULTS, string='Result')
    error_message = fields.Text(string='Error')
    payment_amount = fields.Float(string='Amount Attempted', digits=(10, 2))
    payment_gateway = fields.Char(string='Gateway Used')
    gateway_tx_id = fields.Char(string='Transaction ID')

    def mark_executed(self, result, error=None, tx_id=None):
        self.ensure_one()
        self.write({'state': 'executed', 'result': result, 'executed_at': fields.Datetime.now(),
                    'error_message': error, 'gateway_tx_id': tx_id})

    def mark_skipped(self, reason='State changed'):
        self.ensure_one()
        self.write({'state': 'skipped', 'result': 'skipped',
                    'executed_at': fields.Datetime.now(), 'error_message': reason})

    @api.model
    def cron_run_dunning(self):
        from odoo.addons.saas_lifecycle.services.dunning_service import DunningService
        return DunningService(self.env).run_dunning_cycle()
