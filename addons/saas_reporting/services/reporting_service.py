from odoo import fields
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class ReportingService:
    def __init__(self, env):
        self.env = env

    def compute_mrr(self):
        """Sum of normalized monthly recurring revenue from active subscriptions."""
        Subscription = self.env['saas.subscription'].sudo()
        active = Subscription.search([('status', '=', 'active')])
        mrr = 0.0
        for sub in active:
            amount = (getattr(sub, 'total_amount', 0.0)
                      or getattr(sub, 'base_amount', 0.0) or 0.0)
            cycle = (sub.billing_cycle or 'monthly').lower() if hasattr(sub, 'billing_cycle') else 'monthly'
            if cycle in ('annual', 'yearly', 'year'):
                mrr += amount / 12.0
            elif cycle in ('quarter', 'quarterly'):
                mrr += amount / 3.0
            else:
                mrr += amount
        return mrr

    def count_subs(self, status):
        return self.env['saas.subscription'].sudo().search_count([('status', '=', status)])

    def count_paying_customers(self):
        return self.env['saas.tenant'].sudo().search_count([('state', '=', 'active')])

    def compute_churn_rate(self):
        Tenant = self.env['saas.tenant'].sudo()
        start_of_month = date.today().replace(day=1)
        beginning = Tenant.search_count([
            ('state', 'in', ['active', 'grace_period']),
            ('create_date', '<', start_of_month)])
        churned = Tenant.search_count([
            ('state', '=', 'cancelled'),
            ('write_date', '>=', start_of_month)])
        if beginning <= 0:
            return 0.0
        return (churned / beginning) * 100.0

    def snapshot_today(self):
        today = fields.Date.today()
        Snapshot = self.env['saas.report.snapshot'].sudo()
        existing = Snapshot.search([('snapshot_date', '=', today)], limit=1)
        mrr = self.compute_mrr()
        vals = {
            'snapshot_date': today,
            'mrr': mrr,
            'arr': mrr * 12,
            'active_subscriptions': self.count_subs('active'),
            'trial_subscriptions': self.count_subs('trial') if self._has_trial_status() else 0,
            'paying_customers': self.count_paying_customers(),
            'churn_rate': self.compute_churn_rate(),
        }
        if existing:
            existing.write(vals)
            return existing
        return Snapshot.create(vals)

    def _has_trial_status(self):
        try:
            fields_def = self.env['saas.subscription']._fields.get('status')
            if not fields_def:
                return False
            return 'trial' in [s[0] for s in fields_def.selection]
        except Exception:
            return False
