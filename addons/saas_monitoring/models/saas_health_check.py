from odoo import models, fields, api


class SaasHealthCheck(models.Model):
    _name = 'saas.health.check'
    _description = 'Health Check Definition'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    check_type = fields.Selection(
        selection=[('http', 'HTTP'), ('tcp', 'TCP'), ('db', 'Database'),
                   ('redis', 'Redis'), ('worker', 'Background Worker'),
                   ('custom', 'Custom Python')],
        string='Check Type', required=True, default='http')
    target_url = fields.Char(string='Target URL / Host')
    expected_status_code = fields.Integer(string='Expected HTTP Status', default=200)
    timeout_seconds = fields.Integer(string='Timeout (s)', default=10)
    interval_minutes = fields.Integer(string='Interval (minutes)', default=5)
    sequence = fields.Integer(default=10)
    last_status = fields.Selection(
        selection=[('up', 'Up'), ('degraded', 'Degraded'),
                   ('down', 'Down'), ('unknown', 'Unknown')],
        string='Last Status', default='unknown', readonly=True, index=True)
    last_response_ms = fields.Integer(string='Last Response (ms)', readonly=True)
    last_checked_at = fields.Datetime(string='Last Checked', readonly=True)
    consecutive_failures = fields.Integer(string='Consecutive Failures', default=0, readonly=True)
    alert_threshold = fields.Integer(string='Alert After N Failures', default=3)
    history_ids = fields.One2many('saas.health.history', 'check_id', string='History')
    uptime_pct_24h = fields.Float(string='Uptime % (24h)', compute='_compute_uptime')
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Check code must be unique.')]

    def _compute_uptime(self):
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        for c in self:
            total = self.env['saas.health.history'].search_count([
                ('check_id', '=', c.id), ('checked_at', '>=', cutoff)])
            up = self.env['saas.health.history'].search_count([
                ('check_id', '=', c.id), ('checked_at', '>=', cutoff),
                ('status', '=', 'up')])
            c.uptime_pct_24h = (up / total * 100.0) if total else 0.0

    @api.model
    def cron_run_health_checks(self):
        from odoo.addons.saas_monitoring.services.health_service import HealthService
        HealthService(self.env).run_due_checks()
