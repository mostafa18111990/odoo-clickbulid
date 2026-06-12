from odoo import models, fields, api

LINE_TYPES = [
    ('subscription', 'Subscription Fee'), ('proration', 'Proration Adjustment'),
    ('overage_user', 'Extra Users'), ('overage_storage', 'Extra Storage'),
    ('setup_fee', 'Setup Fee'), ('addon', 'Marketplace Add-on'),
    ('discount', 'Discount'), ('credit', 'Credit Applied'), ('tax', 'Tax'),
]


class SaasInvoiceLine(models.Model):
    _name = 'saas.invoice.line'
    _description = 'Invoice Line'
    _order = 'sequence, id'

    invoice_id = fields.Many2one('saas.invoice', string='Invoice', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Seq.', default=10)
    line_type = fields.Selection(selection=LINE_TYPES, string='Type', required=True, default='subscription')
    name = fields.Char(string='Description', required=True)
    name_ar = fields.Char(string='الوصف (عربي)')
    period_start = fields.Date(string='Period Start')
    period_end = fields.Date(string='Period End')
    quantity = fields.Float(string='Qty', digits=(10, 4), default=1.0)
    unit_price = fields.Float(string='Unit Price', digits=(10, 2))
    discount_pct = fields.Float(string='Discount %', digits=(5, 2), default=0.0)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True, digits=(10, 2))
    tax_rate_id = fields.Many2one('saas.tax.rate', string='Tax Rate')
    tax_amount = fields.Float(string='Tax', digits=(10, 2), default=0.0)
    total = fields.Float(string='Total', compute='_compute_total', store=True, digits=(10, 2))
    subscription_line_id = fields.Many2one('saas.subscription.line', string='Usage Line', ondelete='set null')

    @api.depends('quantity', 'unit_price', 'discount_pct')
    def _compute_subtotal(self):
        for rec in self:
            gross = rec.quantity * rec.unit_price
            rec.subtotal = round(gross - gross * rec.discount_pct / 100, 2)

    @api.depends('subtotal', 'tax_amount')
    def _compute_total(self):
        for rec in self:
            rec.total = round(rec.subtotal + rec.tax_amount, 2)
