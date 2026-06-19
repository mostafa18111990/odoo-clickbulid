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
