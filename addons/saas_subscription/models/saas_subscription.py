from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

SUB_STATUS = [
    ('trial', 'Trial'), ('active', 'Active'), ('past_due', 'Past Due'),
    ('paused', 'Paused'), ('cancelled', 'Cancelled'), ('expired', 'Expired'),
]
BILLING_CYCLES = [('monthly', 'Monthly'), ('yearly', 'Yearly')]
CURRENCIES = [('SAR', 'SAR'), ('AED', 'AED'), ('USD', 'USD'), ('EGP', 'EGP'), ('KWD', 'KWD')]
PAYMENT_GATEWAYS = [
    ('paytabs', 'PayTabs'), ('paymob', 'PayMob'), ('stripe', 'Stripe'),
    ('hyperpay', 'HyperPay'), ('myfatoorah', 'MyFatoorah'), ('manual', 'Manual / Offline'),
]


class SaasSubscription(models.Model):
    _name = 'saas.subscription'
    _description = 'SaaS Subscription'
    _inherit = ['saas.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Subscription', compute='_compute_display_name', store=True)

    @api.depends('tenant_id', 'plan_id', 'billing_cycle', 'status')
    def _compute_display_name(self):
        for rec in self:
            t = rec.tenant_id.subdomain if rec.tenant_id else '?'
            p = rec.plan_id.name if rec.plan_id else '?'
            rec.display_name = f'{t} - {p} ({rec.billing_cycle or "?"})'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    plan_id = fields.Many2one('saas.plan', string='Plan', required=True, ondelete='restrict')
    status = fields.Selection(selection=SUB_STATUS, string='Status', default='trial',
                              required=True, tracking=True, index=True)
    is_current = fields.Boolean(string='Current Subscription', default=True, index=True)
    billing_cycle = fields.Selection(selection=BILLING_CYCLES, string='Billing Cycle',
                                     required=True, default='monthly')
    currency = fields.Selection(selection=CURRENCIES, string='Currency', required=True, default='SAR')

    trial_start = fields.Date(string='Trial Start')
    trial_end = fields.Date(string='Trial End')
    current_period_start = fields.Date(string='Period Start')
    current_period_end = fields.Date(string='Period End')
    next_renewal_date = fields.Date(string='Next Renewal', index=True)
    cancelled_at = fields.Date(string='Cancelled At')
    cancel_at_period_end = fields.Boolean(string='Cancel at Period End', default=False)
    paused_at = fields.Date(string='Paused At')
    resumed_at = fields.Date(string='Resumed At')

    base_amount = fields.Float(string='Base Amount', digits=(10, 2))
    discount_amount = fields.Float(string='Discount Amount', digits=(10, 2), default=0.0)
    discount_pct = fields.Float(string='Discount %', digits=(5, 2), default=0.0)
    coupon_code = fields.Char(string='Coupon Code Applied', index=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True, digits=(10, 2))
    credit_balance = fields.Float(string='Credit Balance', digits=(10, 2), default=0.0)

    payment_gateway = fields.Selection(selection=PAYMENT_GATEWAYS, string='Payment Gateway')
    gateway_subscription_id = fields.Char(string='Gateway Subscription ID', index=True)
    gateway_customer_id = fields.Char(string='Gateway Customer ID', index=True)
    last_payment_date = fields.Date(string='Last Payment Date')
    last_payment_amount = fields.Float(string='Last Payment Amount', digits=(10, 2))
    last_payment_tx_id = fields.Char(string='Last Transaction ID')
    failed_payment_count = fields.Integer(string='Failed Payment Count', default=0)

    line_ids = fields.One2many('saas.subscription.line', 'subscription_id', string='Usage Lines')
    history_ids = fields.One2many('saas.subscription.history', 'subscription_id', string='History')
    pending_change_ids = fields.One2many('saas.plan.change', 'subscription_id', string='Pending Plan Changes')

    unbilled_overage = fields.Float(string='Unbilled Overage', compute='_compute_unbilled_overage',
                                    store=True, digits=(10, 2))
    days_to_renewal = fields.Integer(string='Days to Renewal', compute='_compute_days_to_renewal')

    @api.depends('base_amount', 'discount_amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = max(0, round(rec.base_amount - rec.discount_amount, 2))

    @api.depends('line_ids.amount', 'line_ids.billed')
    def _compute_unbilled_overage(self):
        for rec in self:
            rec.unbilled_overage = sum(rec.line_ids.filtered(lambda l: not l.billed).mapped('amount'))

    @api.depends('next_renewal_date')
    def _compute_days_to_renewal(self):
        today = date.today()
        for rec in self:
            rec.days_to_renewal = max(0, (rec.next_renewal_date - today).days) if rec.next_renewal_date else 0

    @api.constrains('base_amount')
    def _check_amount(self):
        for rec in self:
            if rec.base_amount < 0:
                raise ValidationError('Base amount cannot be negative.')

    @api.constrains('credit_balance')
    def _check_credit(self):
        for rec in self:
            if rec.credit_balance < 0:
                raise ValidationError('Credit balance cannot be negative.')

    def get_renewal_amount(self):
        self.ensure_one()
        return round(max(0, self.total_amount - self.credit_balance + self.unbilled_overage), 2)

    def apply_credit(self, amount, description=None):
        self.ensure_one()
        if amount <= 0:
            raise UserError('Credit amount must be positive.')
        self.credit_balance = round(self.credit_balance + amount, 2)
        self.env['saas.subscription.history'].record(self, 'credit_applied', credit_amount=amount,
            description=description or f'Credit of {amount} {self.currency} applied')

    def consume_credit(self, amount):
        self.ensure_one()
        if self.credit_balance <= 0:
            return amount
        used = min(self.credit_balance, amount)
        self.credit_balance = round(self.credit_balance - used, 2)
        return round(amount - used, 2)

    def record_payment_success(self, amount, tx_id, gateway=None):
        self.ensure_one()
        self.write({'last_payment_date': date.today(), 'last_payment_amount': amount,
                    'last_payment_tx_id': tx_id, 'failed_payment_count': 0, 'status': 'active'})
        self.env['saas.subscription.history'].record(self, 'payment_success', amount=amount,
            description=f'Payment received: {amount} {self.currency} (TX: {tx_id})')

    def record_payment_failure(self, error):
        self.ensure_one()
        self.write({'failed_payment_count': self.failed_payment_count + 1, 'status': 'past_due'})
        self.env['saas.subscription.history'].record(self, 'payment_failed',
            description=f'Payment failed: {error}')

    def get_period_days(self):
        self.ensure_one()
        if self.current_period_start and self.current_period_end:
            return (self.current_period_end - self.current_period_start).days
        return 30 if self.billing_cycle == 'monthly' else 365

    def get_days_remaining(self):
        self.ensure_one()
        return max(0, (self.current_period_end - date.today()).days) if self.current_period_end else 0

    @api.model
    def cron_run_renewals(self):
        from odoo.addons.saas_subscription.services.renewal_service import RenewalService
        return RenewalService(self.env).run_renewals()

    @api.model
    def cron_usage_snapshot(self):
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        svc = SubscriptionService(self.env)
        for sub in self.search([('status', '=', 'active')]):
            try:
                svc.record_usage_snapshot(sub)
            except Exception as e:
                _logger.error('Usage snapshot failed: %s', e)

    def action_view_history(self):
        self.ensure_one()
        return {'name': _('Subscription History'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.subscription.history', 'view_mode': 'list',
                'domain': [('subscription_id', '=', self.id)]}

    def action_view_usage_lines(self):
        self.ensure_one()
        return {'name': _('Usage Lines'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.subscription.line', 'view_mode': 'list',
                'domain': [('subscription_id', '=', self.id)]}
