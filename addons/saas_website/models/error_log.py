from odoo import models, fields
from datetime import datetime, timedelta


class SaasErrorLog(models.Model):
    _name = 'saas.error.log'
    _description = 'Platform Error Logs'
    _order = 'create_date DESC'

    code = fields.Char('Error Code', required=True, index=True)
    message = fields.Text('Error Message')
    details = fields.Text('Full Details (JSON)')
    severity = fields.Selection([
        ('info', 'معلومة'),
        ('warning', 'تحذير'),
        ('critical', 'حرج'),
    ], default='warning')
    resolved = fields.Boolean('تم الحل', default=False)
    resolution_notes = fields.Text('ملاحظات الحل')
    affected_tenant_id = fields.Many2one('saas.tenant', 'المستأجر المتأثر')

    def action_resolve(self):
        """Mark error as resolved."""
        self.write({'resolved': True})

    def action_retry(self):
        """Attempt to recover from error (depends on error type)."""
        for log in self:
            if log.code == 'TENANT_PROVISION':
                # Retry provisioning
                tenant = log.affected_tenant_id
                if tenant:
                    tenant._queue_local_provision()
            elif log.code == 'EMAIL_SEND':
                # Retry email delivery
                pass
            elif log.code == 'PAYMENT_FAILED':
                # Trigger payment retry
                pass

    def get_recent_errors(self, hours=24, severity='critical'):
        """Get recent critical errors."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.search([
            ('create_date', '>=', cutoff),
            ('severity', '=', severity),
            ('resolved', '=', False)
        ])

    def cleanup_old_logs(self, days=90):
        """Delete logs older than X days."""
        cutoff = datetime.now() - timedelta(days=days)
        old_logs = self.search([
            ('create_date', '<', cutoff),
            ('resolved', '=', True)
        ])
        old_logs.unlink()
