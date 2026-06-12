from odoo import models, fields


class SaasTicketPriority(models.Model):
    _name = 'saas.ticket.priority'
    _description = 'Ticket Priority'
    _order = 'sequence'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(default=10)
    color = fields.Char(string='Color', default='#6b7280')
    icon = fields.Char(string='Icon', default='fa-flag')
    response_hours = fields.Integer(string='Response Time (hours)', default=8)
    resolution_hours = fields.Integer(string='Resolution Time (hours)', default=24)
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Priority code must be unique.')]
