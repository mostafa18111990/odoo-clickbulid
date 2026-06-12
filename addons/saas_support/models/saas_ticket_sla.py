from odoo import models, fields


class SaasTicketSla(models.Model):
    _name = 'saas.ticket.sla'
    _description = 'SLA Configuration'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True)
    priority_id = fields.Many2one('saas.ticket.priority', string='Priority', required=True)
    plan_id = fields.Many2one('saas.plan', string='Plan')
    response_hours = fields.Integer(string='Response Hours', required=True)
    resolution_hours = fields.Integer(string='Resolution Hours', required=True)
    business_hours_only = fields.Boolean(string='Business Hours Only', default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
