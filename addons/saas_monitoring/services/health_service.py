import time
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, env):
        self.env = env

    def run_due_checks(self):
        from odoo import fields
        now = fields.Datetime.now()
        Check = self.env['saas.health.check'].sudo()
        due = Check.search([('active', '=', True)])
        for c in due:
            if c.last_checked_at and \
               (now - c.last_checked_at).total_seconds() < (c.interval_minutes or 5) * 60:
                continue
            self.execute(c)

    def execute(self, check):
        from odoo import fields
        t0 = time.time()
        status = 'unknown'
        err = None
        status_code = 0
        try:
            if check.check_type == 'http' and check.target_url:
                status, status_code = self._http_check(check)
            elif check.check_type == 'db':
                status = self._db_check()
            else:
                status = 'up'
        except Exception as e:
            status = 'down'
            err = str(e)
            _logger.warning('Health check %s failed: %s', check.code, e)
        elapsed = int((time.time() - t0) * 1000)
        self.env['saas.health.history'].sudo().create({
            'check_id': check.id, 'status': status,
            'response_ms': elapsed, 'error_message': err,
            'status_code': status_code,
        })
        vals = {'last_status': status, 'last_response_ms': elapsed,
                'last_checked_at': fields.Datetime.now()}
        if status == 'up':
            vals['consecutive_failures'] = 0
        else:
            vals['consecutive_failures'] = (check.consecutive_failures or 0) + 1
        check.write(vals)
        if status != 'up' and vals['consecutive_failures'] >= (check.alert_threshold or 3):
            self._raise_alert(check, status, err)
        return status

    def _http_check(self, check):
        try:
            import urllib.request
            req = urllib.request.Request(check.target_url, method='GET')
            with urllib.request.urlopen(req, timeout=check.timeout_seconds or 10) as r:
                code = r.status
                if code == (check.expected_status_code or 200):
                    return 'up', code
                if 200 <= code < 400:
                    return 'degraded', code
                return 'down', code
        except Exception:
            raise

    def _db_check(self):
        self.env.cr.execute('SELECT 1')
        return 'up' if self.env.cr.fetchone() else 'down'

    def _raise_alert(self, check, status, err):
        self.env['saas.security.event'].sudo().create({
            'event_type': 'other', 'severity': 'high',
            'description': f'Health check {check.code} is {status}: {err or "no detail"}'})
