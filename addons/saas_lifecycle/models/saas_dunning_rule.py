from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaasDunningRule(models.Model):
    _name = 'saas.dunning.rule'
    _description = 'SaaS Dunning Rule'
    _order = 'sequence, attempt_number'
    _rec_name = 'name'

    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string='Priority', default=10)
    attempt_number = fields.Integer(string='Attempt Number', required=True, default=1)
    applies_to_state = fields.Selection(
        selection=[('grace_period', 'Grace Period'), ('suspended', 'Suspended')],
        string='Applies to State', required=True, default='grace_period')
    delay_days = fields.Integer(string='Execute After (days)', required=True, default=0)
    plan_ids = fields.Many2many('saas.plan', string='Apply to Plans')
    billing_cycle = fields.Selection(
        selection=[('monthly', 'Monthly Only'), ('yearly', 'Yearly Only'), ('', 'All Billing Cycles')],
        string='Billing Cycle Filter', default='')
    action = fields.Selection(
        selection=[('send_email', 'Send Email Only'), ('retry_payment', 'Retry Payment'),
                   ('suspend', 'Suspend Tenant'), ('cancel', 'Cancel Tenant')],
        string='Action', required=True, default='retry_payment')
    email_template_id = fields.Many2one('mail.template', string='Email Template',
                                        domain=[('model', '=', 'saas.tenant')])
    send_email = fields.Boolean(string='Also Send Email', default=True)
    is_final = fields.Boolean(string='Final Rule (Max Attempts)', default=False)

    @api.constrains('delay_days')
    def _check_delay(self):
        for rec in self:
            if rec.delay_days < 0:
                raise ValidationError('Delay cannot be negative.')

    @api.constrains('attempt_number')
    def _check_attempt(self):
        for rec in self:
            if rec.attempt_number < 1:
                raise ValidationError('Attempt number must be at least 1.')

    def matches_tenant(self, tenant):
        if self.plan_ids and tenant.plan_id not in self.plan_ids:
            return False
        if self.billing_cycle and tenant.billing_cycle != self.billing_cycle:
            return False
        return True
