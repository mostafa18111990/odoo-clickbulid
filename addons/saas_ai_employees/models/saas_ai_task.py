import json
import logging
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.claude_client import ClaudeApiError, ClaudeClient


_logger = logging.getLogger(__name__)


SENSITIVE_ACTIONS = {'publish_post', 'reply', 'create_quote'}
CONTROLLED_FIELDS = {
    'state', 'output_text', 'started_at', 'completed_at', 'attempts',
    'next_retry_at', 'external_ref', 'error_message', 'usage_id',
    'approved_by', 'approved_at', 'idempotency_key',
}


class SaasAiTask(models.Model):
    _name = 'saas.ai.task'
    _description = 'AI Employee Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, scheduled_at, id'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', related='employee_id.company_id', store=True, index=True)
    employee_id = fields.Many2one(
        'saas.ai.employee', required=True, ondelete='restrict', tracking=True,
        index=True)
    channel_id = fields.Many2one(
        'saas.ai.social.channel', ondelete='restrict', tracking=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]")
    lead_id = fields.Many2one('crm.lead', ondelete='set null', index=True)
    task_type = fields.Selection([
        ('qualify_lead', 'Qualify Lead'),
        ('follow_up', 'Sales Follow-up'),
        ('create_quote', 'Prepare Quote'),
        ('content_plan', 'Content Plan'),
        ('draft_post', 'Draft Social Post'),
        ('publish_post', 'Publish Social Post'),
        ('reply', 'Reply to Message or Comment'),
        ('analytics', 'Analytics Summary'),
    ], required=True, index=True, tracking=True)
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent'),
    ], default='1', required=True, index=True)
    input_text = fields.Text(required=True)
    context_json = fields.Text(
        default='{}', help='Non-secret JSON context for Claude.')
    output_text = fields.Text(readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Queued'),
        ('running', 'Running'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, index=True)
    scheduled_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    attempts = fields.Integer(default=0, readonly=True)
    max_attempts = fields.Integer(default=3, required=True)
    next_retry_at = fields.Datetime(readonly=True, index=True)
    idempotency_key = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True)
    external_ref = fields.Char(readonly=True, copy=False)
    error_message = fields.Text(readonly=True)
    usage_id = fields.Many2one('saas.ai.usage', readonly=True, ondelete='set null')
    approved_by = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)

    _idempotency_unique = models.Constraint(
        'UNIQUE(idempotency_key)', 'The task idempotency key must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group(
            'saas_ai_employees.group_ai_employee_manager')
        for vals in vals_list:
            controlled = CONTROLLED_FIELDS.intersection(vals)
            controlled.discard('idempotency_key')
            if not is_manager and (
                controlled or vals.get('state', 'draft') != 'draft'
            ):
                raise AccessError(_('Only AI managers can set execution fields.'))
        return super().create(vals_list)

    def write(self, vals):
        if (
            CONTROLLED_FIELDS.intersection(vals)
            and not self.env.context.get('ai_task_transition')
            and not self.env.user.has_group(
                'saas_ai_employees.group_ai_employee_manager')
        ):
            raise AccessError(_('Only AI managers can set execution fields.'))
        return super().write(vals)

    @api.constrains('context_json')
    def _check_context_json(self):
        for task in self:
            try:
                value = json.loads(task.context_json or '{}')
            except (TypeError, ValueError) as exc:
                raise ValidationError('Context must be valid JSON.') from exc
            if not isinstance(value, dict):
                raise ValidationError('Context JSON must contain an object.')

    @api.constrains('max_attempts')
    def _check_max_attempts(self):
        for task in self:
            if task.max_attempts < 1 or task.max_attempts > 10:
                raise ValidationError('Maximum attempts must be between 1 and 10.')

    def action_queue(self):
        for task in self:
            if task.state not in ('draft', 'failed'):
                raise UserError(_('Only draft or failed tasks can be queued.'))
            task.with_context(ai_task_transition=True).write({
                'state': 'pending', 'error_message': False,
                'next_retry_at': False,
            })

    def action_approve(self):
        if not self.env.user.has_group(
            'saas_ai_employees.group_ai_employee_manager'):
            raise AccessError(_('Only AI managers can approve tasks.'))
        for task in self:
            if task.state != 'awaiting_approval':
                raise UserError(_('Only tasks awaiting approval can be approved.'))
            task.write({
                'state': 'approved', 'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })

    def action_mark_done(self):
        if not self.env.user.has_group(
            'saas_ai_employees.group_ai_employee_manager'):
            raise AccessError(_('Only AI managers can execute approved tasks.'))
        for task in self:
            if task.state != 'approved':
                raise UserError(_('The task must be approved first.'))
            task.write({'state': 'done', 'completed_at': fields.Datetime.now()})

    def action_cancel(self):
        self.filtered(lambda task: task.state not in ('done', 'cancelled')).with_context(
            ai_task_transition=True).write({
            'state': 'cancelled',
        })

    def _approval_required(self):
        self.ensure_one()
        if self.employee_id.autonomy == 'draft':
            return True
        return (
            self.employee_id.autonomy == 'approval'
            and self.task_type in SENSITIVE_ACTIONS
        )

    def _build_prompt(self):
        self.ensure_one()
        context = json.loads(self.context_json or '{}')
        payload = {
            'task_type': self.task_type,
            'channel': self.channel_id.platform if self.channel_id else None,
            'language': self.employee_id.language,
            'request': self.input_text,
            'context': context,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _execute_claude(self):
        self.ensure_one()
        provider = self.employee_id.provider_id
        started = fields.Datetime.now()
        self.with_context(ai_task_transition=True).write({
            'state': 'running', 'started_at': started,
            'attempts': self.attempts + 1, 'error_message': False,
        })
        client = ClaudeClient.from_provider(provider)
        result = client.create_message(
            system=self.employee_id.system_prompt,
            prompt=self._build_prompt(),
            model=self.employee_id.model or provider.default_model,
            max_tokens=provider.max_tokens,
            temperature=provider.temperature,
        )
        usage = self.env['saas.ai.usage'].sudo().create({
            'provider_id': provider.id,
            'user_id': self.env.uid,
            'request_type': 'chat',
            'model': result['model'],
            'input_tokens': result['input_tokens'],
            'output_tokens': result['output_tokens'],
            'cost': (
                provider.cost_per_1k_input_tokens * result['input_tokens'] / 1000.0
                + provider.cost_per_1k_output_tokens * result['output_tokens'] / 1000.0
            ),
            'response_time_ms': result['response_time_ms'],
            'status': 'success',
        })
        state = 'awaiting_approval' if self._approval_required() else 'done'
        self.with_context(ai_task_transition=True).write({
            'output_text': result['text'],
            'usage_id': usage.id,
            'state': state,
            'completed_at': fields.Datetime.now() if state == 'done' else False,
            'next_retry_at': False,
        })

    def _record_failure(self, exc):
        self.ensure_one()
        retry = self.attempts < self.max_attempts
        delay_minutes = min(60, 2 ** max(self.attempts, 1))
        self.with_context(ai_task_transition=True).write({
            'state': 'pending' if retry else 'failed',
            'next_retry_at': (
                fields.Datetime.now() + timedelta(minutes=delay_minutes)
                if retry else False
            ),
            'error_message': str(exc)[:1000],
        })

    @api.model
    def _cron_process_pending(self, batch_size=5):
        now = fields.Datetime.now()
        day_start = fields.Datetime.start_of(now, 'day')
        tasks = self.search([
            ('state', '=', 'pending'),
            ('scheduled_at', '<=', now),
            '|', ('next_retry_at', '=', False), ('next_retry_at', '<=', now),
        ], order='priority desc, scheduled_at, id', limit=batch_size)
        for task in tasks:
            processed_today = self.search_count([
                ('employee_id', '=', task.employee_id.id),
                ('started_at', '>=', day_start),
            ])
            if processed_today >= task.employee_id.daily_task_limit:
                continue
            try:
                with self.env.cr.savepoint():
                    task._execute_claude()
            except ClaudeApiError as exc:
                _logger.warning('Claude task %s failed: %s', task.id, exc)
                task._record_failure(exc)
            except Exception:
                _logger.exception('Unexpected AI task failure for task %s', task.id)
                task._record_failure(_('Unexpected worker error.'))
