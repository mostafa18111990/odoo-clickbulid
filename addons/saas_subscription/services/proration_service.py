from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class ProrationService:
    def __init__(self, env):
        self.env = env

    def calculate_upgrade(self, old_plan, new_plan, cycle, period_start, period_end):
        today = date.today()
        days_remaining = max(0, (period_end - today).days)
        days_in_period = max(1, (period_end - period_start).days)
        old_daily = self._daily_rate(old_plan, cycle)
        new_daily = self._daily_rate(new_plan, cycle)
        extra = round(max(0, new_daily - old_daily) * days_remaining, 2)
        return {'extra_charge': extra, 'days_remaining': days_remaining, 'days_in_period': days_in_period,
                'old_daily_rate': round(old_daily, 4), 'new_daily_rate': round(new_daily, 4),
                'calculation': f'({new_daily:.4f} - {old_daily:.4f}) x {days_remaining}d = {extra} SAR'}

    def calculate_downgrade(self, old_plan, new_plan, cycle, period_start, period_end):
        today = date.today()
        days_remaining = max(0, (period_end - today).days)
        days_in_period = max(1, (period_end - period_start).days)
        old_daily = self._daily_rate(old_plan, cycle)
        new_daily = self._daily_rate(new_plan, cycle)
        credit = round(max(0, old_daily - new_daily) * days_remaining, 2)
        return {'credit_amount': credit, 'days_remaining': days_remaining, 'days_in_period': days_in_period,
                'old_daily_rate': round(old_daily, 4), 'new_daily_rate': round(new_daily, 4),
                'calculation': f'({old_daily:.4f} - {new_daily:.4f}) x {days_remaining}d = {credit} SAR credit'}

    def calculate_cycle_change(self, plan, current_cycle, new_cycle, period_start, period_end):
        today = date.today()
        days_remaining = max(0, (period_end - today).days)
        old_daily = self._daily_rate(plan, current_cycle)
        credit = round(old_daily * days_remaining, 2)
        new_base = plan.get_effective_yearly_price() if new_cycle == 'yearly' else plan.monthly_price
        net = max(0, round(new_base - credit, 2))
        return {'net_charge': net, 'credit_amount': credit, 'new_base': new_base,
                'days_remaining': days_remaining,
                'calculation': f'New {new_cycle} {new_base} - credit {credit} = {net} SAR'}

    def calculate_renewal(self, subscription):
        base = subscription.total_amount
        overage = subscription.unbilled_overage
        credit = min(subscription.credit_balance, base + overage)
        net = max(0, round(base + overage - credit, 2))
        return {'base_amount': base, 'overage_amount': overage, 'credit_used': credit,
                'net_amount': net, 'currency': subscription.currency,
                'breakdown': [
                    {'label': 'Plan Fee', 'amount': base},
                    {'label': 'Overages', 'amount': overage},
                    {'label': 'Credits Used', 'amount': -credit},
                    {'label': 'Total Due', 'amount': net}]}

    def _daily_rate(self, plan, cycle):
        if cycle == 'yearly':
            return plan.get_effective_yearly_price() / 365.0
        return plan.monthly_price / 30.0
