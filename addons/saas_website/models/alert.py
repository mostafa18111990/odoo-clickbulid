from odoo import models, fields
from datetime import datetime, timedelta


class SaasAlert(models.Model):
    _name = 'saas.alert'
    _description = 'Platform Alerts'
    _order = 'create_date DESC'

    code = fields.Char('Alert Code', required=True, index=True)
    message = fields.Text('Alert Message')
    severity = fields.Selection([
        ('info', 'معلومة'),
        ('warning', 'تحذير'),
        ('critical', 'حرج'),
    ], default='warning', index=True)
    details = fields.Text('Full Details (JSON)')
    acknowledged = fields.Boolean('تم الإقرار', default=False)
    acknowledged_by = fields.Many2one('res.users', 'أقرّ بواسطة')
    acknowledged_date = fields.Datetime('تاريخ الإقرار')

    def action_acknowledge(self):
        """Mark alert as acknowledged."""
        for alert in self:
            alert.write({
                'acknowledged': True,
                'acknowledged_by': self.env.user.id,
                'acknowledged_date': datetime.now(),
            })

    def get_unacknowledged_alerts(self, severity='critical'):
        """Get unacknowledged alerts."""
        return self.search([
            ('acknowledged', '=', False),
            ('severity', '=', severity),
        ])

    def get_recent_alerts(self, hours=24):
        """Get alerts from last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.search([
            ('create_date', '>=', cutoff),
        ])

    def cleanup_old_alerts(self, days=30):
        """Delete acknowledged alerts older than X days."""
        cutoff = datetime.now() - timedelta(days=days)
        old_alerts = self.search([
            ('create_date', '<', cutoff),
            ('acknowledged', '=', True),
        ])
        old_alerts.unlink()

    def cron_check_platform_health(self):
        """Run the platform health checks and raise alerts for failures.

        Self-contained: runs on `self.env` (cron context has no HTTP request,
        so the request-bound HealthCheck/AlertNotifier services can't be used
        here) and only checks things reachable from inside the container.
        """
        import os
        failures = []

        # 1. Database connectivity (our own cursor must answer).
        try:
            self.env.cr.execute('SELECT 1')
        except Exception as e:
            failures.append(('HEALTH_CHECK_DATABASE', f'Master DB query failed: {e}'))

        # 2. Provisioning queue: failed requests or requests stuck > 15 min.
        req_dir = '/mnt/cert-requests'
        try:
            if os.path.isdir(req_dir):
                import time
                now = time.time()
                errors = [f for f in os.listdir(req_dir) if f.endswith('.error')]
                stale = [f for f in os.listdir(req_dir)
                         if f.endswith('.req') and now - os.path.getmtime(os.path.join(req_dir, f)) > 900]
                if errors:
                    failures.append(('HEALTH_CHECK_PROVISIONING_QUEUE',
                                     f'Failed requests: {", ".join(sorted(errors)[:10])}'))
                if stale:
                    failures.append(('HEALTH_CHECK_PROVISIONING_QUEUE',
                                     f'Requests stuck >15min (sweeper down?): {", ".join(sorted(stale)[:10])}'))
        except Exception as e:
            failures.append(('HEALTH_CHECK_PROVISIONING_QUEUE', f'Queue check failed: {e}'))

        # 3. Disk space on the data volume.
        try:
            st = os.statvfs('/var/lib/odoo')
            free_pct = st.f_bavail / st.f_blocks * 100
            if free_pct < 10:
                failures.append(('HEALTH_CHECK_DISK',
                                 f'Data volume nearly full: {free_pct:.1f}% free'))
        except Exception:
            pass

        Alert = self.sudo()
        for code, message in failures:
            # Don't spam: skip if an identical unacknowledged alert exists.
            if not Alert.search_count([('code', '=', code), ('acknowledged', '=', False)]):
                Alert.create({'code': code, 'message': message, 'severity': 'critical'})
        return {'healthy': not failures, 'failures': len(failures)}
