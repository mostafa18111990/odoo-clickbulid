from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaasAiEmployee(models.Model):
    _name = 'saas.ai.employee'
    _description = 'AI Employee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    role = fields.Selection([
        ('sales', 'Sales'),
        ('marketing', 'Marketing'),
        ('community', 'Social Community'),
        ('analytics', 'Analytics'),
    ], required=True, tracking=True)
    provider_id = fields.Many2one(
        'saas.ai.provider', required=True, ondelete='restrict',
        domain="[('code', '=', 'anthropic'), ('active', '=', True)]")
    model = fields.Char(
        help='Optional Claude model override. Leave empty to use the provider default.')
    system_prompt = fields.Text(required=True)
    language = fields.Selection([
        ('ar', 'Arabic'), ('en', 'English'), ('ar_en', 'Arabic and English'),
    ], default='ar_en', required=True)
    autonomy = fields.Selection([
        ('draft', 'Draft Only'),
        ('approval', 'Act After Approval'),
        ('auto', 'Automatic Within Guardrails'),
    ], default='approval', required=True, tracking=True)
    daily_task_limit = fields.Integer(default=50, required=True)
    channel_ids = fields.Many2many(
        'saas.ai.social.channel', 'saas_ai_employee_channel_rel',
        'employee_id', 'channel_id', string='Channels')
    task_count = fields.Integer(compute='_compute_task_count')

    @api.depends('role')
    def _compute_task_count(self):
        grouped = self.env['saas.ai.task']._read_group(
            [('employee_id', 'in', self.ids)], ['employee_id'], ['__count'])
        counts = {employee.id: count for employee, count in grouped}
        for employee in self:
            employee.task_count = counts.get(employee.id, 0)

    @api.constrains('daily_task_limit')
    def _check_daily_task_limit(self):
        for employee in self:
            if employee.daily_task_limit < 1 or employee.daily_task_limit > 1000:
                raise ValidationError('Daily task limit must be between 1 and 1000.')

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'saas_ai_employees.action_saas_ai_task')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action
