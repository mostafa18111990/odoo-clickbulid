from odoo import fields
from datetime import timedelta, date
import logging

_logger = logging.getLogger(__name__)


class ChurnService:
    def __init__(self, env):
        self.env = env

    def calculate_monthly_churn_rate(self, year, month):
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        active_start = self.env['saas.tenant'].search_count([
            ('state', '=', 'active'),
            ('activated_at', '<', fields.Datetime.from_string(f'{start} 00:00:00'))])
        cancelled = self.env['saas.tenant'].search_count([
            ('state', 'in', ['cancelled', 'archived', 'deleted']),
            ('cancelled_at', '>=', fields.Datetime.from_string(f'{start} 00:00:00')),
            ('cancelled_at', '<', fields.Datetime.from_string(f'{end} 00:00:00'))])
        return round(cancelled / active_start * 100, 2) if active_start else 0.0

    def get_revenue_at_risk(self):
        states = ['grace_period', 'suspended', 'pending_payment']
        tenants = self.env['saas.tenant'].search([('state', 'in', states), ('plan_id', '!=', False)])
        total = 0.0
        by_state = {}
        for t in tenants:
            if t.plan_id:
                mrr = t.plan_id.monthly_price
                total += mrr
                by_state[t.state] = by_state.get(t.state, 0) + mrr
        return {'total_mrr_at_risk': round(total, 2), 'tenant_count': len(tenants),
                'by_state': by_state, 'currency': 'SAR'}

    def get_winback_candidates(self, max_days_since_cancel=90):
        cutoff = fields.Datetime.now() - timedelta(days=max_days_since_cancel)
        candidates = self.env['saas.tenant'].search([
            ('state', 'in', ['cancelled', 'archived']), ('winback_eligible', '=', True),
            ('winback_triggered_at', '=', False), ('cancelled_at', '>=', cutoff)])
        return [{'tenant_id': t.id, 'subdomain': t.subdomain, 'email': t.customer_email,
                 'plan': t.plan_id.name if t.plan_id else '',
                 'cancel_reason': t.cancellation_reason_id.name if t.cancellation_reason_id else 'Unknown',
                 'days_since_cancel': (fields.Datetime.now() - t.cancelled_at).days if t.cancelled_at else 0}
                for t in candidates]

    def get_churn_by_reason(self, days=90):
        cutoff = fields.Datetime.now() - timedelta(days=days)
        cancelled = self.env['saas.tenant'].search([
            ('state', 'in', ['cancelled', 'archived', 'deleted']), ('cancelled_at', '>=', cutoff)])
        counts = {}
        for t in cancelled:
            r = t.cancellation_reason_id
            key = r.name if r else 'Unknown'
            if key not in counts:
                counts[key] = {'name': key, 'category': r.churn_category if r else 'other', 'count': 0}
            counts[key]['count'] += 1
        return sorted(counts.values(), key=lambda x: x['count'], reverse=True)
