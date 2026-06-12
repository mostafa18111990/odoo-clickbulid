from odoo import fields
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class SlaService:
    def __init__(self, env):
        self.env = env

    def cron_check_sla(self):
        now = fields.Datetime.now()
        soon = now + timedelta(hours=1)
        response_breached = self.env['saas.ticket'].sudo().search([
            ('state', 'not in', ['resolved', 'closed']),
            ('sla_first_response_at', '=', False),
            ('sla_response_deadline', '<', now),
            ('sla_response_breached', '=', False)])
        for ticket in response_breached:
            ticket.write({'sla_response_breached': True, 'sla_breached': True})
            self._publish_breach(ticket, 'response')
        resolution_breached = self.env['saas.ticket'].sudo().search([
            ('state', 'not in', ['resolved', 'closed']),
            ('sla_resolution_deadline', '<', now),
            ('sla_resolution_breached', '=', False)])
        for ticket in resolution_breached:
            ticket.write({'sla_resolution_breached': True, 'sla_breached': True})
            self._publish_breach(ticket, 'resolution')
        at_risk = self.env['saas.ticket'].sudo().search([
            ('state', 'not in', ['resolved', 'closed']),
            ('sla_first_response_at', '=', False),
            ('sla_response_deadline', '>=', now),
            ('sla_response_deadline', '<=', soon)])
        _logger.info('SLA cron: %d response, %d resolution, %d at-risk',
                     len(response_breached), len(resolution_breached), len(at_risk))

    def _publish_breach(self, ticket, breach_type):
        self.env['saas.event'].sudo()._publish(
            event_type='ticket.created', model='saas.ticket', record_id=ticket.id,
            payload={'ticket_id': ticket.id, 'number': ticket.name, 'breach_type': breach_type,
                     'tenant_id': ticket.tenant_id.id if ticket.tenant_id else None},
            tenant_id=ticket.tenant_id.id if ticket.tenant_id else None)
