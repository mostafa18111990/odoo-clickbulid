from odoo import models, fields, api

LINE_TYPES = [
    ('extra_user', 'Extra Users'), ('extra_storage', 'Extra Storage (GB)'),
    ('addon', 'Marketplace Add-on'), ('one_time', 'One-Time Charge'),
]


class SaasSubscriptionLine(models.Model):
    _name = 'saas.subscription.line'
    _description = 'Subscription Usage Line'
    _order = 'period_start desc, id'

    subscription_id = fields.Many2one('saas.subscription', string='Subscription', required=True,
                                      ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', related='subscription_id.tenant_id', store=True, index=True)
    line_type = fields.Selection(selection=LINE_TYPES, string='Type', required=True, index=True)
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', digits=(10, 2), default=0.0)
    unit_price = fields.Float(string='Unit Price (SAR)', digits=(10, 4))
    amount = fields.Float(string='Line Total (SAR)', compute='_compute_amount', store=True, digits=(10, 2))
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    billed = fields.Boolean(string='Billed', default=False, index=True)
    snapshot_users = fields.Integer(string='Actual Users')
    snapshot_storage_mb = fields.Float(string='Actual Storage (MB)', digits=(10, 0))
    plan_limit = fields.Float(string='Plan Limit')
    overage = fields.Float(string='Overage')

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.unit_price, 2)
