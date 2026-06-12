from odoo import fields
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class RenewalService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_subscription.services.proration_service import ProrationService
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        from odoo.addons.saas_core.services.event_bus_service import EventBusService
        self.proration = ProrationService(env)
        self.svc = SubscriptionService(env)
        self.events = EventBusService(env)

    def run_renewals(self):
        today = date.today()
        renewed = cancelled = errors = 0
        reminded = self._send_renewal_reminders(today)
        due = self.env['saas.subscription'].search([
            ('status', '=', 'active'), ('next_renewal_date', '<=', today),
            ('cancel_at_period_end', '=', False)])
        for sub in due:
            try:
                self._process_renewal(sub)
                renewed += 1
            except Exception as e:
                errors += 1
                _logger.error('Renewal failed for %s: %s', sub.display_name, e)
        cancelled = self._process_end_of_period_cancellations(today)
        self._apply_deferred_changes(today)
        _logger.info('RenewalService: %d renewed, %d reminded, %d cancelled, %d errors',
                     renewed, reminded, cancelled, errors)
        return {'renewed': renewed, 'reminded': reminded, 'cancelled': cancelled, 'errors': errors}

    def _process_renewal(self, subscription):
        tenant = subscription.tenant_id
        try:
            self.svc.record_usage_snapshot(subscription)
        except Exception as e:
            _logger.warning('Usage snapshot failed for %s: %s', tenant.subdomain, e)
        calc = self.proration.calculate_renewal(subscription)
        net_amount = calc['net_amount']
        if subscription.credit_balance > 0:
            net_amount = subscription.consume_credit(net_amount)
        self.env['saas.subscription.history'].record(subscription, 'renewed', amount=net_amount,
            credit_amount=calc.get('credit_used', 0), new_plan_id=subscription.plan_id.id,
            new_cycle=subscription.billing_cycle, description=f'Auto-renewal: {net_amount} {subscription.currency}')
        if net_amount <= 0:
            self._extend_period(subscription)
        else:
            self.events.publish('payment.retry.scheduled', payload={'tenant_id': tenant.id,
                'subscription_id': subscription.id, 'amount': net_amount, 'currency': subscription.currency,
                'gateway': subscription.payment_gateway, 'reason': 'subscription_renewal'},
                tenant_id=tenant.id)
        self.events.publish('subscription.renewed', payload={'tenant_id': tenant.id,
            'subscription_id': subscription.id, 'amount': net_amount, 'plan': subscription.plan_id.code},
            tenant_id=tenant.id)

    def _extend_period(self, subscription):
        today = date.today()
        _, new_end = self.svc._next_period_dates(subscription.billing_cycle, today)
        subscription.write({'current_period_start': today, 'current_period_end': new_end,
            'next_renewal_date': new_end + timedelta(days=1), 'status': 'active', 'failed_payment_count': 0})
        subscription.line_ids.filtered(lambda l: not l.billed).write({'billed': True})

    def _send_renewal_reminders(self, today):
        reminder_date = today + timedelta(days=7)
        subs = self.env['saas.subscription'].search([
            ('status', '=', 'active'), ('next_renewal_date', '=', reminder_date)])
        for sub in subs:
            self.events.publish('subscription.renewed', payload={'tenant_id': sub.tenant_id.id,
                'type': 'reminder', 'days_until': 7, 'amount': sub.get_renewal_amount(),
                'renewal_date': str(reminder_date)}, tenant_id=sub.tenant_id.id)
        return len(subs)

    def _process_end_of_period_cancellations(self, today):
        to_cancel = self.env['saas.subscription'].search([
            ('cancel_at_period_end', '=', True), ('current_period_end', '<=', today)])
        for sub in to_cancel:
            try:
                self.svc.cancel(sub, at_period_end=False)
            except Exception as e:
                _logger.error('End-of-period cancel failed for %s: %s', sub.display_name, e)
        return len(to_cancel)

    def _apply_deferred_changes(self, today):
        due = self.env['saas.plan.change'].search([
            ('status', '=', 'pending'), ('apply_immediately', '=', False),
            ('effective_date', '<=', today)])
        for change in due:
            try:
                self.svc._execute_plan_change(change)
            except Exception as e:
                _logger.error('Deferred change failed for %s: %s', change.display_name, e)

    def on_renewal_payment_success(self, subscription, amount, tx_id):
        subscription.record_payment_success(amount, tx_id)
        self._extend_period(subscription)

    def on_renewal_payment_failure(self, subscription, error):
        subscription.record_payment_failure(error)
        from odoo.addons.saas_core.services.tenant_service import TenantService
        TenantService(self.env).handle_payment_failure(subscription.tenant_id, 'renewal', error)
