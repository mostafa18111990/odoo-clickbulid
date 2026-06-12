class MetricsService:
    def __init__(self, env):
        self.env = env

    def sample_now(self):
        Snapshot = self.env['saas.metric.snapshot'].sudo()
        metrics = self.collect()
        for name, value, labels in metrics:
            Snapshot.create({'metric_name': name, 'value': value, 'labels': labels or ''})

    def collect(self):
        """Returns list of (metric_name, value, labels)."""
        out = []
        # Tenants
        Tenant = self.env['saas.tenant'].sudo()
        for state in ('trial', 'active', 'suspended', 'cancelled'):
            out.append(('saas_tenants_total', Tenant.search_count([('state', '=', state)]),
                        f'state={state}'))
        # Subscriptions
        Sub = self.env['saas.subscription'].sudo()
        out.append(('saas_subscriptions_active',
                    Sub.search_count([('status', '=', 'active')]), ''))
        # Tickets
        Ticket = self.env['saas.ticket'].sudo()
        for st in ('new', 'in_progress', 'resolved'):
            out.append(('saas_tickets_total',
                        Ticket.search_count([('state', '=', st)]),
                        f'state={st}'))
        out.append(('saas_tickets_sla_breached',
                    Ticket.search_count([('sla_breached', '=', True),
                                         ('state', 'not in', ['resolved', 'closed'])]), ''))
        # Health checks
        Health = self.env['saas.health.check'].sudo()
        for st in ('up', 'degraded', 'down'):
            out.append(('saas_health_checks',
                        Health.search_count([('last_status', '=', st)]),
                        f'status={st}'))
        # API request count last hour
        from datetime import timedelta
        from odoo import fields
        cutoff = fields.Datetime.now() - timedelta(hours=1)
        ApiLog = self.env['saas.api.request.log'].sudo()
        out.append(('saas_api_requests_1h',
                    ApiLog.search_count([('create_date', '>=', cutoff)]), ''))
        out.append(('saas_api_errors_1h',
                    ApiLog.search_count([('create_date', '>=', cutoff),
                                         ('status_code', '>=', 400)]), ''))
        # Snapshot MRR if available
        Snapshot = self.env['saas.report.snapshot'].sudo().search(
            [], order='snapshot_date desc', limit=1)
        if Snapshot:
            out.append(('saas_mrr', Snapshot.mrr or 0.0, ''))
            out.append(('saas_arr', Snapshot.arr or 0.0, ''))
            out.append(('saas_active_subs', Snapshot.active_subscriptions or 0, ''))
            out.append(('saas_paying_customers', Snapshot.paying_customers or 0, ''))
            out.append(('saas_churn_rate', Snapshot.churn_rate or 0.0, ''))
        return out

    def prometheus_format(self):
        """Render current metrics in Prometheus exposition text format."""
        lines = []
        seen = set()
        for name, value, labels in self.collect():
            if name not in seen:
                lines.append(f'# TYPE {name} gauge')
                seen.add(name)
            if labels:
                label_str = ','.join([f'{k}="{v}"' for k, v in
                                      (p.split('=', 1) for p in labels.split(',') if '=' in p)])
                lines.append(f'{name}{{{label_str}}} {value}')
            else:
                lines.append(f'{name} {value}')
        return '\n'.join(lines) + '\n'
