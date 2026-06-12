from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

JOB_STATES = [
    ('pending', 'Pending'), ('running', 'Running'), ('done', 'Done'),
    ('failed', 'Failed'), ('cancelled', 'Cancelled'),
]
JOB_TYPES = [
    ('provision', 'Provision Tenant'), ('suspend', 'Suspend Tenant'),
    ('activate', 'Activate Tenant'), ('delete', 'Delete Tenant'),
    ('backup', 'Backup Tenant'), ('restore', 'Restore Tenant'),
    ('upgrade', 'Upgrade Tenant'),
]


class SaasProvisioningJob(models.Model):
    _name = 'saas.provisioning.job'
    _description = 'SaaS Provisioning Job'
    _order = 'create_date desc'
    _rec_name = 'job_type'

    job_type = fields.Selection(selection=JOB_TYPES, string='Job Type', required=True, index=True)
    state = fields.Selection(selection=JOB_STATES, string='State', default='pending',
                             required=True, index=True, tracking=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    external_job_id = fields.Char(string='FastAPI Job ID', index=True)
    attempt_count = fields.Integer(string='Attempts', default=0)
    max_attempts = fields.Integer(string='Max Attempts', default=3)
    next_retry_at = fields.Datetime(string='Next Retry At')
    last_error = fields.Text(string='Last Error')
    payload = fields.Text(string='Input Payload (JSON)')
    result = fields.Text(string='Result (JSON)')
    started_at = fields.Datetime(string='Started At', readonly=True)
    completed_at = fields.Datetime(string='Completed At', readonly=True)
    duration_seconds = fields.Integer(string='Duration (s)', compute='_compute_duration', store=True)

    @api.depends('started_at', 'completed_at')
    def _compute_duration(self):
        for rec in self:
            if rec.started_at and rec.completed_at:
                rec.duration_seconds = int((rec.completed_at - rec.started_at).total_seconds())
            else:
                rec.duration_seconds = 0

    def action_start(self):
        self.ensure_one()
        self.write({'state': 'running', 'started_at': fields.Datetime.now(),
                    'attempt_count': self.attempt_count + 1})

    def action_complete(self, result=None):
        self.ensure_one()
        import json
        self.write({'state': 'done', 'completed_at': fields.Datetime.now(),
                    'result': json.dumps(result or {}, default=str), 'last_error': False})

    def action_fail(self, error, retry=True):
        self.ensure_one()
        if retry and self.attempt_count < self.max_attempts:
            backoff = 2 ** self.attempt_count
            self.write({'state': 'pending', 'last_error': error,
                        'next_retry_at': fields.Datetime.now() + timedelta(minutes=backoff)})
        else:
            self.write({'state': 'failed', 'completed_at': fields.Datetime.now(), 'last_error': error})

    @api.model
    def cron_retry_pending_jobs(self):
        now = fields.Datetime.now()
        pending = self.search(['&', ('state', '=', 'pending'),
                               '|', ('next_retry_at', '=', False), ('next_retry_at', '<=', now)])
        from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
        bridge = ProvisioningBridgeService(self.env)
        for job in pending:
            try:
                bridge.execute_job(job)
            except Exception as e:
                _logger.error('Job retry failed for job %d: %s', job.id, e)
                job.action_fail(str(e), retry=True)
