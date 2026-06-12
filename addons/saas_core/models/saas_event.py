from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)

EVENT_TYPES = [
    ('tenant.lead.created', 'Lead: Created'),
    ('tenant.trial.started', 'Trial: Started'),
    ('tenant.trial.reminder', 'Trial: Reminder Sent'),
    ('tenant.trial.expired', 'Trial: Expired'),
    ('tenant.activated', 'Tenant: Activated'),
    ('tenant.suspended', 'Tenant: Suspended'),
    ('tenant.grace_period.started', 'Tenant: Grace Period Started'),
    ('tenant.grace_period.expired', 'Tenant: Grace Period Expired'),
    ('tenant.cancelled', 'Tenant: Cancelled'),
    ('tenant.archived', 'Tenant: Archived'),
    ('tenant.deleted', 'Tenant: Deleted'),
    ('tenant.reactivated', 'Tenant: Reactivated'),
    ('provisioning.started', 'Provisioning: Started'),
    ('provisioning.completed', 'Provisioning: Completed'),
    ('provisioning.failed', 'Provisioning: Failed'),
    ('subscription.created', 'Subscription: Created'),
    ('subscription.renewed', 'Subscription: Renewed'),
    ('subscription.upgraded', 'Subscription: Plan Upgraded'),
    ('subscription.downgraded', 'Subscription: Plan Downgraded'),
    ('subscription.cancelled', 'Subscription: Cancelled'),
    ('subscription.expired', 'Subscription: Expired'),
    ('payment.received', 'Payment: Received'),
    ('payment.failed', 'Payment: Failed'),
    ('payment.refunded', 'Payment: Refunded'),
    ('payment.retry.scheduled', 'Payment: Retry Scheduled'),
    ('invoice.generated', 'Invoice: Generated'),
    ('invoice.paid', 'Invoice: Paid'),
    ('invoice.overdue', 'Invoice: Overdue'),
    ('backup.completed', 'Backup: Completed'),
    ('backup.failed', 'Backup: Failed'),
    ('restore.completed', 'Restore: Completed'),
    ('domain.verified', 'Domain: Verified'),
    ('domain.ssl.issued', 'Domain: SSL Issued'),
    ('ticket.created', 'Ticket: Created'),
    ('ticket.resolved', 'Ticket: Resolved'),
    ('security.login.failed', 'Security: Login Failed'),
    ('security.2fa.enabled', 'Security: 2FA Enabled'),
]


class SaasEvent(models.Model):
    _name = 'saas.event'
    _description = 'SaaS Event Log'
    _order = 'create_date desc'
    _rec_name = 'event_type'

    event_type = fields.Selection(selection=EVENT_TYPES, string='Event Type', required=True, index=True)
    model = fields.Char(string='Source Model', index=True)
    record_id = fields.Integer(string='Source Record ID', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', string='Triggered By', default=lambda self: self.env.uid, readonly=True)
    payload = fields.Text(string='Payload (JSON)', readonly=True)
    processed = fields.Boolean(string='Processed', default=False, index=True)
    error_message = fields.Text(string='Processing Error', readonly=True)
    payload_preview = fields.Text(string='Payload Preview', compute='_compute_payload_preview')

    @api.depends('payload')
    def _compute_payload_preview(self):
        for rec in self:
            if rec.payload:
                try:
                    rec.payload_preview = json.dumps(json.loads(rec.payload), indent=2, ensure_ascii=False)[:500]
                except Exception:
                    rec.payload_preview = rec.payload[:500]
            else:
                rec.payload_preview = ''

    @api.model
    def _publish(self, event_type, model=None, record_id=None, payload=None, tenant_id=None):
        valid_types = [t[0] for t in EVENT_TYPES]
        if event_type not in valid_types:
            _logger.warning('saas.event._publish: unknown event type %r', event_type)
        event = self.create({
            'event_type': event_type, 'model': model, 'record_id': record_id,
            'tenant_id': tenant_id,
            'payload': json.dumps(payload or {}, default=str, ensure_ascii=False),
            'user_id': self.env.uid, 'processed': False,
        })
        self.env.cr.precommit.add(lambda: self._dispatch_handlers(event.id))
        return event

    @api.model
    def _dispatch_handlers(self, event_id):
        from odoo.addons.saas_core.services.event_bus_service import EventBusService
        try:
            event = self.browse(event_id).exists()
            if event:
                EventBusService(self.env)._dispatch(event)
                event.processed = True
        except Exception as e:
            _logger.error('Event dispatch failed for event %d: %s', event_id, e)
            try:
                self.browse(event_id).write({'error_message': str(e)})
            except Exception:
                pass

    def write(self, vals):
        allowed = {'processed', 'error_message'}
        if not set(vals.keys()).issubset(allowed):
            raise UserError('SaaS Events are immutable.')
        return super().write(vals)

    def unlink(self):
        raise UserError('SaaS Events cannot be deleted.')
