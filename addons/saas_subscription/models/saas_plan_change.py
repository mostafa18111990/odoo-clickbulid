from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

BILLING_CYCLES = [('monthly', 'Monthly'), ('yearly', 'Yearly')]
CHANGE_TYPES = [
    ('upgrade', 'Upgrade'), ('downgrade', 'Downgrade'),
    ('cycle_change', 'Billing Cycle Change'), ('reactivation', 'Reactivation'),
]
CHANGE_STATUS = [('pending', 'Pending'), ('applied', 'Applied'), ('cancelled', 'Cancelled')]


class SaasPlanChange(models.Model):
    _name = 'saas.plan.change'
    _description = 'SaaS Plan Change Request'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('tenant_id', 'change_type', 'to_plan_id')
    def _compute_display_name(self):
        for rec in self:
            t = rec.tenant_id.subdomain if rec.tenant_id else '?'
            p = rec.to_plan_id.name if rec.to_plan_id else '?'
            rec.display_name = f'{t}: {rec.change_type} -> {p}'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    subscription_id = fields.Many2one('saas.subscription', string='Subscription', required=True, ondelete='cascade')
    change_type = fields.Selection(selection=CHANGE_TYPES, string='Change Type', required=True, index=True)
    status = fields.Selection(selection=CHANGE_STATUS, string='Status', default='pending',
                              required=True, tracking=True, index=True)
    from_plan_id = fields.Many2one('saas.plan', string='From Plan')
    to_plan_id = fields.Many2one('saas.plan', string='To Plan', required=True)
    from_cycle = fields.Selection(BILLING_CYCLES, string='From Cycle')
    to_cycle = fields.Selection(BILLING_CYCLES, string='To Cycle')
    apply_immediately = fields.Boolean(string='Apply Immediately', default=True)
    effective_date = fields.Date(string='Effective Date')
    applied_at = fields.Datetime(string='Applied At', readonly=True)
    requested_by = fields.Selection(
        selection=[('customer', 'Customer (portal)'), ('admin', 'Admin'), ('system', 'System (automated)')],
        string='Requested By', default='admin')
    proration_amount = fields.Float(string='Proration Amount', digits=(10, 2))
    days_remaining = fields.Integer(string='Days Remaining in Period')
    days_in_period = fields.Integer(string='Total Days in Period')
    credit_to_apply = fields.Float(string='Credit to Apply', digits=(10, 2))
    customer_note = fields.Text(string='Customer Note')
    admin_note = fields.Text(string='Admin Note')

    @api.constrains('from_plan_id', 'to_plan_id', 'change_type')
    def _check_plan_hierarchy(self):
        for rec in self:
            if not rec.from_plan_id or not rec.to_plan_id:
                continue
            fp, tp = rec.from_plan_id.monthly_price, rec.to_plan_id.monthly_price
            if rec.change_type == 'upgrade' and tp <= fp:
                raise ValidationError(f'Upgrade: "{rec.to_plan_id.name}" is not more expensive than "{rec.from_plan_id.name}".')
            if rec.change_type == 'downgrade' and tp >= fp:
                raise ValidationError(f'Downgrade: "{rec.to_plan_id.name}" is not less expensive than "{rec.from_plan_id.name}".')

    def action_apply(self):
        self.ensure_one()
        if self.status != 'pending':
            raise UserError(_('Only pending plan changes can be applied.'))
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        SubscriptionService(self.env)._execute_plan_change(self)

    def action_cancel_change(self):
        self.ensure_one()
        if self.status != 'pending':
            raise UserError(_('Only pending plan changes can be cancelled.'))
        self.write({'status': 'cancelled'})
