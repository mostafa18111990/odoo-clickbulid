from odoo import models, fields, api
from odoo.exceptions import UserError

LOG_TYPES = [
    ('lifecycle_rule', 'Lifecycle Rule Executed'), ('dunning_attempt', 'Dunning Attempt'),
    ('winback', 'Win-Back Triggered'), ('manual', 'Manual Override'), ('cron', 'Cron Job'),
]
LOG_RESULTS = [
    ('success', 'Success'), ('skipped', 'Skipped'), ('failed', 'Failed'), ('no_action', 'No Action Needed'),
]


class SaasLifecycleLog(models.Model):
    _name = 'saas.lifecycle.log'
    _description = 'SaaS Lifecycle Execution Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Log Entry', compute='_compute_display_name', store=True)

    @api.depends('tenant_id', 'log_type', 'result')
    def _compute_display_name(self):
        for rec in self:
            t = rec.tenant_id.subdomain if rec.tenant_id else '?'
            rec.display_name = f'{t} - {rec.log_type} ({rec.result})'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    log_type = fields.Selection(selection=LOG_TYPES, string='Type', required=True, index=True)
    result = fields.Selection(selection=LOG_RESULTS, string='Result', required=True, index=True)
    lifecycle_rule_id = fields.Many2one('saas.lifecycle.rule', string='Rule', ondelete='set null')
    dunning_attempt_id = fields.Many2one('saas.dunning.attempt', string='Dunning Attempt', ondelete='set null')
    description = fields.Text(string='Details', required=True)
    state_before = fields.Char(string='State Before')
    state_after = fields.Char(string='State After')
    error_message = fields.Text(string='Error')

    def write(self, vals):
        raise UserError('Lifecycle logs are immutable.')

    def unlink(self):
        raise UserError('Lifecycle logs cannot be deleted.')

    @api.model
    def log(self, tenant, log_type, result, description, rule=None, attempt=None,
            state_before=None, state_after=None, error=None):
        return self.sudo().create({
            'tenant_id': tenant.id, 'log_type': log_type, 'result': result,
            'description': description, 'lifecycle_rule_id': rule.id if rule else False,
            'dunning_attempt_id': attempt.id if attempt else False,
            'state_before': state_before or tenant.state, 'state_after': state_after,
            'error_message': error})
