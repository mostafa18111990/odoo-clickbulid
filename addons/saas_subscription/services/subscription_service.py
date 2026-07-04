from odoo import fields, _
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

try:
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


class SubscriptionService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_subscription.services.proration_service import ProrationService
        from odoo.addons.saas_core.services.event_bus_service import EventBusService
        from odoo.addons.saas_core.services.audit_service import AuditService
        self.proration = ProrationService(env)
        self.events = EventBusService(env)
        self.audit = AuditService(env)

    def create_trial(self, tenant, plan, cycle='monthly', currency='SAR'):
        config = self.env['saas.config']._get_config()
        today = date.today()
        trial_end = today + timedelta(days=config.trial_days)
        # Per-user plans: amount = purchased seats × price per user.
        # Flat plans: price_for_users falls back to the classic plan price.
        seats = getattr(tenant, 'user_count', 0) or (plan.max_users or 0)
        base = plan.price_for_users(seats, cycle)
        sub = self.env['saas.subscription'].create({
            'tenant_id': tenant.id, 'plan_id': plan.id, 'status': 'trial', 'billing_cycle': cycle,
            'currency': currency, 'trial_start': today, 'trial_end': trial_end,
            'current_period_start': today, 'current_period_end': trial_end,
            'next_renewal_date': trial_end, 'base_amount': base, 'is_current': True})
        tenant.with_context(bypass_fsm=True).write({'current_subscription_id': sub.id})
        self.env['saas.subscription.history'].record(sub, 'trial_started', new_plan_id=plan.id,
            new_cycle=cycle, period_start=today, period_end=trial_end,
            description=f'Trial started: {plan.name} ({cycle}), ends {trial_end}')
        self.events.publish('subscription.created', payload={'tenant_id': tenant.id,
            'subscription_id': sub.id, 'plan': plan.code, 'cycle': cycle, 'trial_end': str(trial_end)},
            tenant_id=tenant.id)
        return sub

    def convert_to_paid(self, subscription, gateway, tx_id, amount_paid, gateway_subscription_id=None):
        today = date.today()
        period_start, period_end = self._next_period_dates(subscription.billing_cycle, today)
        subscription.write({'status': 'active', 'current_period_start': period_start,
            'current_period_end': period_end, 'next_renewal_date': period_end + timedelta(days=1),
            'payment_gateway': gateway, 'gateway_subscription_id': gateway_subscription_id,
            'last_payment_date': today, 'last_payment_amount': amount_paid, 'last_payment_tx_id': tx_id,
            'failed_payment_count': 0})
        self.env['saas.subscription.history'].record(subscription, 'converted', amount=amount_paid,
            new_plan_id=subscription.plan_id.id, new_cycle=subscription.billing_cycle,
            period_start=period_start, period_end=period_end,
            description=f'Trial converted: {amount_paid} {subscription.currency}')
        if subscription.tenant_id.state != 'active':
            subscription.tenant_id.action_activate()
        self.events.publish('subscription.created', payload={'tenant_id': subscription.tenant_id.id,
            'subscription_id': subscription.id, 'amount': amount_paid, 'gateway': gateway},
            tenant_id=subscription.tenant_id.id)
        return subscription

    def upgrade(self, subscription, new_plan, immediate=True, admin_note=None):
        old_plan = subscription.plan_id
        if new_plan.monthly_price <= old_plan.monthly_price:
            raise UserError(_('Cannot upgrade to "%s": not a higher plan.', new_plan.name))
        proration_data = {}
        if immediate and subscription.current_period_start and subscription.current_period_end:
            proration_data = self.proration.calculate_upgrade(old_plan, new_plan,
                subscription.billing_cycle, subscription.current_period_start, subscription.current_period_end)
        change = self.env['saas.plan.change'].create({
            'tenant_id': subscription.tenant_id.id, 'subscription_id': subscription.id,
            'change_type': 'upgrade', 'status': 'pending', 'from_plan_id': old_plan.id,
            'to_plan_id': new_plan.id, 'from_cycle': subscription.billing_cycle,
            'to_cycle': subscription.billing_cycle, 'apply_immediately': immediate,
            'effective_date': date.today() if immediate else subscription.next_renewal_date,
            'proration_amount': proration_data.get('extra_charge', 0),
            'days_remaining': proration_data.get('days_remaining', 0),
            'days_in_period': proration_data.get('days_in_period', 0), 'admin_note': admin_note})
        if immediate:
            self._execute_plan_change(change)
        return change

    def downgrade(self, subscription, new_plan, immediate=False, customer_note=None):
        old_plan = subscription.plan_id
        if new_plan.monthly_price >= old_plan.monthly_price:
            raise UserError(_('Cannot downgrade to "%s": not a lower plan.', new_plan.name))
        credit_to_apply = 0.0
        if immediate and subscription.current_period_start and subscription.current_period_end:
            cd = self.proration.calculate_downgrade(old_plan, new_plan, subscription.billing_cycle,
                subscription.current_period_start, subscription.current_period_end)
            credit_to_apply = cd.get('credit_amount', 0)
        change = self.env['saas.plan.change'].create({
            'tenant_id': subscription.tenant_id.id, 'subscription_id': subscription.id,
            'change_type': 'downgrade', 'status': 'pending', 'from_plan_id': old_plan.id,
            'to_plan_id': new_plan.id, 'from_cycle': subscription.billing_cycle,
            'to_cycle': subscription.billing_cycle, 'apply_immediately': immediate,
            'effective_date': date.today() if immediate else subscription.next_renewal_date,
            'credit_to_apply': credit_to_apply, 'customer_note': customer_note})
        if immediate:
            self._execute_plan_change(change)
        return change

    def _execute_plan_change(self, change):
        subscription = change.subscription_id
        old_plan, new_plan = change.from_plan_id, change.to_plan_id
        new_base = (new_plan.get_effective_yearly_price() if subscription.billing_cycle == 'yearly'
                    else new_plan.monthly_price)
        subscription.write({'plan_id': new_plan.id, 'base_amount': new_base})
        if change.credit_to_apply > 0:
            subscription.apply_credit(change.credit_to_apply,
                f'Downgrade credit: {old_plan.name} -> {new_plan.name}')
        change.tenant_id.with_context(bypass_fsm=True).write({'plan_id': new_plan.id})
        event_type = 'upgraded' if change.change_type == 'upgrade' else 'downgraded'
        self.env['saas.subscription.history'].record(subscription, event_type,
            old_plan_id=old_plan.id, new_plan_id=new_plan.id, proration_amount=change.proration_amount,
            credit_amount=change.credit_to_apply,
            description=f'{change.change_type.title()}: {old_plan.name} -> {new_plan.name}')
        self.events.publish(f'subscription.{event_type}', payload={'tenant_id': change.tenant_id.id,
            'subscription_id': subscription.id, 'from_plan': old_plan.code, 'to_plan': new_plan.code,
            'proration': change.proration_amount, 'credit': change.credit_to_apply},
            tenant_id=change.tenant_id.id)
        if change.change_type == 'upgrade' and change.proration_amount > 0:
            net = subscription.consume_credit(change.proration_amount)
            if net > 0:
                self.events.publish('payment.retry.scheduled', payload={'tenant_id': change.tenant_id.id,
                    'subscription_id': subscription.id, 'amount': net,
                    'reason': f'Upgrade proration: {old_plan.name} -> {new_plan.name}',
                    'gateway': subscription.payment_gateway, 'currency': subscription.currency},
                    tenant_id=change.tenant_id.id)
        change.write({'status': 'applied', 'applied_at': fields.Datetime.now()})

    def change_cycle(self, subscription, new_cycle):
        if subscription.billing_cycle == new_cycle:
            raise UserError(_('Already on %s billing.', new_cycle))
        calc = {'net_charge': 0, 'credit_amount': 0}
        if subscription.current_period_start and subscription.current_period_end:
            calc = self.proration.calculate_cycle_change(subscription.plan_id, subscription.billing_cycle,
                new_cycle, subscription.current_period_start, subscription.current_period_end)
        today = date.today()
        period_start, period_end = self._next_period_dates(new_cycle, today)
        new_base = (subscription.plan_id.get_effective_yearly_price() if new_cycle == 'yearly'
                    else subscription.plan_id.monthly_price)
        old_cycle = subscription.billing_cycle
        subscription.write({'billing_cycle': new_cycle, 'base_amount': new_base,
            'current_period_start': today, 'current_period_end': period_end,
            'next_renewal_date': period_end + timedelta(days=1)})
        self.env['saas.subscription.history'].record(subscription, 'cycle_changed',
            old_cycle=old_cycle, new_cycle=new_cycle, amount=calc.get('net_charge', 0),
            credit_amount=calc.get('credit_amount', 0),
            description=f'Billing cycle: {old_cycle} -> {new_cycle}')
        net = calc.get('net_charge', 0)
        if net > 0:
            net2 = subscription.consume_credit(net)
            if net2 > 0:
                self.events.publish('payment.retry.scheduled', payload={'tenant_id': subscription.tenant_id.id,
                    'amount': net2, 'reason': f'Cycle change {old_cycle} -> {new_cycle}',
                    'gateway': subscription.payment_gateway}, tenant_id=subscription.tenant_id.id)
        return subscription

    def cancel(self, subscription, at_period_end=True, reason_id=None, note=None):
        today = date.today()
        if at_period_end:
            subscription.write({'cancel_at_period_end': True,
                'cancelled_at': subscription.current_period_end or today})
            desc = f'Set to cancel at period end ({subscription.current_period_end})'
        else:
            subscription.write({'status': 'cancelled', 'is_current': False, 'cancelled_at': today})
            subscription.tenant_id.action_cancel(reason_id=reason_id, note=note,
                cancelled_by='customer' if self.env.user else 'system')
            desc = 'Subscription cancelled immediately'
        self.env['saas.subscription.history'].record(subscription, 'cancelled', description=desc)
        self.events.publish('subscription.cancelled', payload={'tenant_id': subscription.tenant_id.id,
            'subscription_id': subscription.id, 'at_period_end': at_period_end, 'reason_id': reason_id},
            tenant_id=subscription.tenant_id.id)
        return subscription

    def pause(self, subscription, admin_note=None):
        if subscription.status not in ('active', 'past_due'):
            raise UserError(_('Only active subscriptions can be paused.'))
        subscription.write({'status': 'paused', 'paused_at': date.today()})
        self.env['saas.subscription.history'].record(subscription, 'paused',
            description=admin_note or 'Subscription paused')

    def resume(self, subscription, admin_note=None):
        if subscription.status != 'paused':
            raise UserError(_('Only paused subscriptions can be resumed.'))
        today = date.today()
        _, period_end = self._next_period_dates(subscription.billing_cycle, today)
        subscription.write({'status': 'active', 'resumed_at': today, 'current_period_start': today,
            'current_period_end': period_end, 'next_renewal_date': period_end + timedelta(days=1)})
        self.env['saas.subscription.history'].record(subscription, 'resumed',
            description=admin_note or 'Subscription resumed')

    def apply_coupon(self, subscription, coupon_code):
        coupon = None
        if 'saas.coupon' in self.env:
            coupon = self.env['saas.coupon'].search([('code', '=', coupon_code), ('active', '=', True)], limit=1)
        if not coupon:
            raise UserError(_('Coupon code "%s" is invalid or expired.', coupon_code))
        if coupon.discount_type == 'pct':
            discount = round(subscription.base_amount * coupon.discount_value / 100, 2)
        else:
            discount = min(coupon.discount_value, subscription.base_amount)
        subscription.write({'coupon_code': coupon_code, 'discount_amount': discount,
            'discount_pct': coupon.discount_value if coupon.discount_type == 'pct' else 0})
        self.env['saas.subscription.history'].record(subscription, 'coupon_applied', coupon_code=coupon_code,
            discount_pct=subscription.discount_pct, amount=discount,
            description=f'Coupon "{coupon_code}" applied: {discount} SAR discount')
        return discount

    def record_usage_snapshot(self, subscription):
        tenant = subscription.tenant_id
        plan = subscription.plan_id
        today = date.today()
        actual_users = tenant.users_count or 0
        actual_storage_gb = (tenant.disk_usage_mb or 0) / 1024.0
        max_users = plan.max_users if plan.max_users > 0 else float('inf')
        if actual_users > max_users and plan.extra_user_price > 0:
            extra = actual_users - max_users
            self.env['saas.subscription.line'].create({'subscription_id': subscription.id,
                'line_type': 'extra_user', 'name': f'Extra users: {extra} above {max_users}',
                'quantity': extra, 'unit_price': plan.extra_user_price, 'period_start': today,
                'period_end': subscription.current_period_end or today, 'snapshot_users': actual_users,
                'plan_limit': max_users, 'overage': extra, 'billed': False})
        max_storage_gb = (plan.max_storage_mb or 0) / 1024.0
        if actual_storage_gb > max_storage_gb and plan.extra_storage_price > 0:
            extra_gb = round(actual_storage_gb - max_storage_gb, 2)
            self.env['saas.subscription.line'].create({'subscription_id': subscription.id,
                'line_type': 'extra_storage', 'name': f'Extra storage: {extra_gb} GB above {max_storage_gb:.1f}',
                'quantity': extra_gb, 'unit_price': plan.extra_storage_price, 'period_start': today,
                'period_end': subscription.current_period_end or today,
                'snapshot_storage_mb': tenant.disk_usage_mb or 0, 'plan_limit': max_storage_gb,
                'overage': extra_gb, 'billed': False})

    def _next_period_dates(self, cycle, start):
        if HAS_DATEUTIL:
            end = (start + relativedelta(years=1) if cycle == 'yearly'
                   else start + relativedelta(months=1)) - timedelta(days=1)
        else:
            if cycle == 'yearly':
                end = start.replace(year=start.year + 1) - timedelta(days=1)
            elif start.month == 12:
                end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
            else:
                end = start.replace(month=start.month + 1) - timedelta(days=1)
        return start, end
