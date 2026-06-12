from odoo import models, fields, api
from odoo.exceptions import ValidationError

LIFECYCLE_TRIGGER_STATES = [
    ('lead', 'Lead'), ('trial', 'Trial'), ('pending_payment', 'Pending Payment'),
    ('active', 'Active'), ('grace_period', 'Grace Period'), ('suspended', 'Suspended'),
    ('cancelled', 'Cancelled'), ('archived', 'Archived'),
]
LIFECYCLE_ACTIONS = [
    ('transition', 'Transition State'), ('send_email', 'Send Email Only'),
    ('publish_event', 'Publish Event'), ('winback', 'Trigger Win-Back Campaign'),
]


class SaasLifecycleRule(models.Model):
    _name = 'saas.lifecycle.rule'
    _description = 'SaaS Lifecycle Automation Rule'
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char(string='Rule Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    from_state = fields.Selection(selection=LIFECYCLE_TRIGGER_STATES, string='When Tenant is in State',
                                  required=True, index=True)
    delay_hours = fields.Integer(string='After (hours)', default=0, required=True)
    delay_type = fields.Selection(
        selection=[('since_state_entry', 'Since State Entry'), ('since_last_payment', 'Since Last Payment'),
                   ('since_trial_end', 'Since Trial End')],
        string='Delay Measured From', default='since_state_entry', required=True)
    condition_field = fields.Selection(
        selection=[('', 'No Condition (Always)'), ('billing_cycle', 'Billing Cycle'),
                   ('lead_source', 'Lead Source'), ('plan_id', 'Plan')],
        string='Condition Field', default='')
    condition_value = fields.Char(string='Condition Value')
    action = fields.Selection(selection=LIFECYCLE_ACTIONS, string='Action', required=True, default='transition')
    to_state = fields.Selection(
        selection=[('trial', 'Trial'), ('pending_payment', 'Pending Payment'), ('active', 'Active'),
                   ('grace_period', 'Grace Period'), ('suspended', 'Suspended'), ('cancelled', 'Cancelled'),
                   ('archived', 'Archived'), ('deleted', 'Deleted')],
        string='Transition to State')
    event_to_publish = fields.Char(string='Event Type to Publish')
    email_template_id = fields.Many2one('mail.template', string='Email Template',
                                        domain=[('model', '=', 'saas.tenant')])
    send_email = fields.Boolean(string='Send Email', default=True)
    last_run = fields.Datetime(string='Last Executed', readonly=True)
    execution_count = fields.Integer(string='Total Executions', readonly=True, default=0)

    @api.constrains('action', 'to_state')
    def _check_transition_has_target(self):
        for rec in self:
            if rec.action == 'transition' and not rec.to_state:
                raise ValidationError(f'Rule "{rec.name}": action=transition requires a to_state.')

    @api.constrains('action', 'event_to_publish')
    def _check_event_has_type(self):
        for rec in self:
            if rec.action == 'publish_event' and not rec.event_to_publish:
                raise ValidationError(f'Rule "{rec.name}": action=publish_event requires an event type.')

    @api.constrains('delay_hours')
    def _check_delay(self):
        for rec in self:
            if rec.delay_hours < 0:
                raise ValidationError('Delay cannot be negative.')

    def matches_tenant(self, tenant):
        if not self.condition_field or not self.condition_value:
            return True
        field_val = getattr(tenant, self.condition_field, None)
        if hasattr(field_val, 'id'):
            return str(field_val.id) == self.condition_value
        return str(field_val or '') == self.condition_value

    @api.model
    def cron_run_lifecycle(self):
        from odoo.addons.saas_lifecycle.services.lifecycle_engine import LifecycleEngine
        return LifecycleEngine(self.env).run()

    def get_tenant_entry_time(self, tenant):
        mapping = {
            'since_state_entry': {
                'trial': tenant.trial_started_at, 'active': tenant.activated_at,
                'grace_period': tenant.grace_started_at, 'suspended': tenant.suspended_at,
                'cancelled': tenant.cancelled_at, 'archived': tenant.archived_at,
                'pending_payment': tenant.saas_updated_at,
            },
            'since_last_payment': {'_any': tenant.last_payment_date},
            'since_trial_end': {'_any': tenant.trial_ends_at},
        }
        table = mapping.get(self.delay_type, {})
        return table.get(tenant.state) or table.get('_any')
