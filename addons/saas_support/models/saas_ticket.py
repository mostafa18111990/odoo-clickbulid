from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

TICKET_STATES = [
    ('new', 'New'), ('assigned', 'Assigned'), ('in_progress', 'In Progress'),
    ('waiting_customer', 'Waiting for Customer'), ('resolved', 'Resolved'), ('closed', 'Closed'),
]

ALLOWED_TRANSITIONS = {
    'new': ['assigned', 'in_progress', 'closed'],
    'assigned': ['in_progress', 'waiting_customer', 'resolved', 'closed'],
    'in_progress': ['waiting_customer', 'resolved', 'assigned', 'closed'],
    'waiting_customer': ['in_progress', 'resolved', 'closed'],
    'resolved': ['closed', 'in_progress'],
    'closed': ['in_progress'],
}


class SaasTicket(models.Model):
    _name = 'saas.ticket'
    _description = 'Support Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority_sequence, create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Ticket Number', readonly=True, copy=False, index=True, default='New')
    subject = fields.Char(string='Subject', required=True, tracking=True)
    description = fields.Html(string='Description', sanitize=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', ondelete='cascade', index=True, tracking=True)
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Customer Email', index=True)
    portal_user_id = fields.Many2one('res.users', string='Portal User', ondelete='set null', index=True)
    category_id = fields.Many2one('saas.ticket.category', string='Category', ondelete='restrict', tracking=True)
    priority_id = fields.Many2one('saas.ticket.priority', string='Priority', required=True, tracking=True)
    priority_sequence = fields.Integer(related='priority_id.sequence', store=True)
    state = fields.Selection(selection=TICKET_STATES, string='Status', default='new',
                             required=True, tracking=True, index=True)
    assignee_id = fields.Many2one('res.users', string='Assigned To', ondelete='set null',
                                  tracking=True, index=True)
    team = fields.Selection(
        selection=[('platform', 'Platform'), ('reseller', 'Reseller'), ('escalated', 'Escalated')],
        string='Team', default='platform')
    sla_response_deadline = fields.Datetime(string='Response Deadline', readonly=True, index=True)
    sla_resolution_deadline = fields.Datetime(string='Resolution Deadline', readonly=True, index=True)
    sla_first_response_at = fields.Datetime(string='First Response At', readonly=True)
    sla_resolved_at = fields.Datetime(string='Resolved At', readonly=True)
    sla_breached = fields.Boolean(string='SLA Breached', default=False, index=True)
    sla_response_breached = fields.Boolean(string='Response Breached', default=False)
    sla_resolution_breached = fields.Boolean(string='Resolution Breached', default=False)
    sla_status = fields.Selection(
        selection=[('on_track', 'On Track'), ('at_risk', 'At Risk'),
                   ('breached', 'Breached'), ('met', 'Met')],
        string='SLA Status', compute='_compute_sla_status', store=False)
    message_ids_typed = fields.One2many('saas.ticket.message', 'ticket_id', string='Messages')
    message_count = fields.Integer(string='Messages', compute='_compute_message_count')
    csat_rating = fields.Selection(
        selection=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')],
        string='CSAT Rating')
    csat_comment = fields.Text(string='Customer Feedback')
    csat_submitted_at = fields.Datetime(string='Rated At', readonly=True)
    opened_at = fields.Datetime(string='Opened At', readonly=True, default=fields.Datetime.now)
    closed_at = fields.Datetime(string='Closed At', readonly=True)
    reopened_count = fields.Integer(string='Reopen Count', default=0)

    @api.depends('sla_response_deadline', 'sla_first_response_at', 'state', 'sla_breached')
    def _compute_sla_status(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for rec in self:
            if rec.state in ('resolved', 'closed'):
                rec.sla_status = 'met'
            elif rec.sla_breached:
                rec.sla_status = 'breached'
            elif (rec.sla_response_deadline and rec.sla_response_deadline < now
                  and not rec.sla_first_response_at):
                rec.sla_status = 'at_risk'
            else:
                rec.sla_status = 'on_track'

    @api.depends('message_ids_typed')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids_typed)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('saas.ticket') or 'TICKET-001'
        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket._compute_sla_deadlines()
            ticket._publish_event('ticket.created')
            ticket._apply_auto_assignment()
        return tickets

    def _compute_sla_deadlines(self):
        self.ensure_one()
        if not self.priority_id:
            return
        response_h = self.priority_id.response_hours
        resolution_h = self.priority_id.resolution_hours
        if self.tenant_id and self.tenant_id.plan_id:
            sla = self.env['saas.ticket.sla'].search([
                ('priority_id', '=', self.priority_id.id),
                ('plan_id', '=', self.tenant_id.plan_id.id),
                ('active', '=', True)], limit=1)
            if sla:
                response_h = sla.response_hours
                resolution_h = sla.resolution_hours
        base = self.opened_at or fields.Datetime.now()
        self.write({
            'sla_response_deadline': base + timedelta(hours=response_h),
            'sla_resolution_deadline': base + timedelta(hours=resolution_h)})

    def _apply_auto_assignment(self):
        self.ensure_one()
        if self.assignee_id or not self.category_id:
            return
        if self.category_id.default_assignee_id:
            self.assignee_id = self.category_id.default_assignee_id

    def _validate_transition(self, new_state):
        self.ensure_one()
        if self.state == new_state:
            return
        allowed = ALLOWED_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise UserError(_('Cannot transition ticket from %(f)s to %(t)s. Allowed: %(a)s',
                              f=self.state, t=new_state, a=', '.join(allowed) or 'none'))

    def action_assign(self, user_id=None):
        self.ensure_one()
        user_id = user_id or self.env.uid
        self._validate_transition('assigned')
        self.write({'assignee_id': user_id, 'state': 'assigned'})

    def action_start_work(self):
        self.ensure_one()
        if self.state == 'in_progress':
            return
        if self.state in ('resolved', 'closed'):
            self.reopened_count += 1
            self.write({'sla_resolved_at': False, 'closed_at': False})
        else:
            self._validate_transition('in_progress')
        self.write({'state': 'in_progress',
                    'assignee_id': self.assignee_id.id or self.env.uid})

    def action_wait_customer(self):
        self.ensure_one()
        self._validate_transition('waiting_customer')
        self.write({'state': 'waiting_customer'})

    def action_resolve(self):
        self.ensure_one()
        self._validate_transition('resolved')
        now = fields.Datetime.now()
        self.write({'state': 'resolved', 'sla_resolved_at': now})
        if self.sla_resolution_deadline and now > self.sla_resolution_deadline:
            self.write({'sla_resolution_breached': True, 'sla_breached': True})
        self._publish_event('ticket.resolved')

    def action_close(self):
        self.ensure_one()
        self._validate_transition('closed')
        self.write({'state': 'closed', 'closed_at': fields.Datetime.now()})

    def action_reopen(self):
        self.ensure_one()
        if self.state not in ('resolved', 'closed'):
            raise UserError(_('Only resolved or closed tickets can be reopened.'))
        self.action_start_work()

    def record_first_response(self):
        self.ensure_one()
        if self.sla_first_response_at:
            return
        now = fields.Datetime.now()
        self.write({'sla_first_response_at': now})
        if self.sla_response_deadline and now > self.sla_response_deadline:
            self.write({'sla_response_breached': True, 'sla_breached': True})

    def _publish_event(self, event_type):
        self.env['saas.event'].sudo()._publish(
            event_type=event_type, model='saas.ticket', record_id=self.id,
            payload={'ticket_id': self.id, 'number': self.name, 'subject': self.subject,
                     'tenant_id': self.tenant_id.id if self.tenant_id else None,
                     'priority': self.priority_id.code if self.priority_id else ''},
            tenant_id=self.tenant_id.id if self.tenant_id else None)

    def submit_csat(self, rating, comment=None):
        self.ensure_one()
        if self.state not in ('resolved', 'closed'):
            raise UserError(_('Can only rate resolved tickets.'))
        self.write({'csat_rating': rating, 'csat_comment': comment,
                    'csat_submitted_at': fields.Datetime.now()})

    @api.model
    def cron_check_sla(self):
        from odoo.addons.saas_support.services.sla_service import SlaService
        SlaService(self.env).cron_check_sla()
