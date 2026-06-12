from odoo import models, fields, api


class SaasMetricSnapshot(models.Model):
    _name = 'saas.metric.snapshot'
    _description = 'Metric Snapshot for Time-Series'
    _order = 'sampled_at desc'

    metric_name = fields.Char(string='Metric', required=True, index=True)
    value = fields.Float(string='Value', required=True)
    labels = fields.Char(string='Labels (key=value,…)')
    sampled_at = fields.Datetime(string='Sampled At', required=True,
                                 default=fields.Datetime.now, index=True)

    @api.model
    def cron_sample_metrics(self):
        from odoo.addons.saas_monitoring.services.metrics_service import MetricsService
        MetricsService(self.env).sample_now()

    @api.model
    def cron_prune_old(self):
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(days=30)
        self.search([('sampled_at', '<', cutoff)]).unlink()
