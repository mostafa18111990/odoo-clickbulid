from odoo import models, fields, api

CHURN_CATEGORIES = [
    ('price', 'Price Too High'), ('competitor', 'Moved to Competitor'),
    ('features', 'Missing Features'), ('complexity', 'Too Complex'),
    ('support', 'Poor Support'), ('business', 'Business Closed / Paused'),
    ('trial_only', 'Was Just Testing'), ('other', 'Other'),
]


class SaasCancellationReason(models.Model):
    _name = 'saas.cancellation.reason'
    _description = 'Cancellation Reason'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Reason', required=True, translate=True)
    name_ar = fields.Char(string='السبب (عربي)')
    code = fields.Char(string='Code', required=True, index=True)
    churn_category = fields.Selection(selection=CHURN_CATEGORIES, string='Churn Category', required=True, index=True)
    description = fields.Text(string='Internal Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    eligible_for_winback = fields.Boolean(string='Eligible for Win-Back', default=True)
    winback_delay_days = fields.Integer(string='Win-Back Delay (days)', default=30)
    cancellation_count = fields.Integer(string='Cancellations', compute='_compute_cancellation_count', store=False)

    def _compute_cancellation_count(self):
        for rec in self:
            rec.cancellation_count = self.env['saas.tenant'].search_count([
                ('cancellation_reason_id', '=', rec.id)])
