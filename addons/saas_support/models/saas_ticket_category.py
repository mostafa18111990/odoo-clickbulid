from odoo import models, fields, api


class SaasTicketCategory(models.Model):
    _name = 'saas.ticket.category'
    _description = 'Ticket Category'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    name_ar = fields.Char(string='الاسم')
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description')
    icon = fields.Char(string='Icon', default='fa-life-ring')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    default_assignee_id = fields.Many2one('res.users', string='Default Assignee')
    default_priority_id = fields.Many2one('saas.ticket.priority', string='Default Priority')
    ticket_count = fields.Integer(string='Tickets', compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        for rec in self:
            rec.ticket_count = self.env['saas.ticket'].search_count([('category_id', '=', rec.id)])

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Category code must be unique.')]
