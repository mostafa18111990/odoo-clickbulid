from odoo import models, fields, api, _


class SaasTenantLifecycle(models.Model):
    _name = 'saas.tenant'
    _inherit = 'saas.tenant'

    cancellation_reason_id = fields.Many2one('saas.cancellation.reason', string='Cancellation Reason',
                                             ondelete='set null', index=True)
    cancellation_note = fields.Text(string='Cancellation Note')
    cancelled_by = fields.Selection(
        selection=[('customer', 'Customer (self-service)'), ('admin', 'Admin'), ('system', 'System (automated)')],
        string='Cancelled By')
    winback_eligible = fields.Boolean(string='Eligible for Win-Back', default=True)
    winback_triggered_at = fields.Datetime(string='Win-Back Triggered At', readonly=True)
    winback_converted = fields.Boolean(string='Win-Back Converted', default=False)
    reactivation_count = fields.Integer(string='Reactivation Count', default=0, readonly=True)

    dunning_attempt_ids = fields.One2many('saas.dunning.attempt', 'tenant_id', string='Dunning Attempts')
    dunning_attempt_count = fields.Integer(string='Dunning Attempts', compute='_compute_dunning_count')
    lifecycle_log_ids = fields.One2many('saas.lifecycle.log', 'tenant_id', string='Lifecycle Log')
    lifecycle_log_count = fields.Integer(string='Lifecycle Logs', compute='_compute_lifecycle_log_count')
    churn_cohort = fields.Char(string='Cohort (YYYY-MM)', compute='_compute_churn_cohort', store=True, index=True)

    @api.depends('dunning_attempt_ids')
    def _compute_dunning_count(self):
        for rec in self:
            rec.dunning_attempt_count = len(rec.dunning_attempt_ids)

    @api.depends('lifecycle_log_ids')
    def _compute_lifecycle_log_count(self):
        for rec in self:
            rec.lifecycle_log_count = len(rec.lifecycle_log_ids)

    @api.depends('create_date')
    def _compute_churn_cohort(self):
        for rec in self:
            rec.churn_cohort = rec.create_date.strftime('%Y-%m') if rec.create_date else False

    def action_cancel(self, reason_id=None, note=None, cancelled_by='admin'):
        vals = {'cancelled_by': cancelled_by}
        if reason_id:
            vals['cancellation_reason_id'] = reason_id
        if note:
            vals['cancellation_note'] = note
        self.with_context(bypass_fsm=True).write(vals)
        result = super().action_cancel()
        self._schedule_winback_if_eligible()
        return result

    def _schedule_winback_if_eligible(self):
        self.ensure_one()
        reason = self.cancellation_reason_id
        if not reason or not reason.eligible_for_winback or not self.winback_eligible:
            return
        self.env['saas.event']._publish(
            event_type='tenant.cancelled', model='saas.tenant', record_id=self.id,
            payload={'tenant_id': self.id, 'subdomain': self.subdomain,
                     'reason': reason.code if reason else 'unknown',
                     'winback_delay': reason.winback_delay_days if reason else 30},
            tenant_id=self.id)

    def action_view_dunning_attempts(self):
        self.ensure_one()
        return {'name': _('Dunning Attempts'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.dunning.attempt', 'view_mode': 'list,form',
                'domain': [('tenant_id', '=', self.id)]}

    def action_view_lifecycle_log(self):
        self.ensure_one()
        return {'name': _('Lifecycle Log'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.lifecycle.log', 'view_mode': 'list',
                'domain': [('tenant_id', '=', self.id)]}
