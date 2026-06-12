from odoo import models, fields, api
from odoo.exceptions import UserError

TX_STATUS = [
    ('pending', 'Pending'), ('processing', 'Processing'), ('success', 'Success'),
    ('failed', 'Failed'), ('refunded', 'Refunded'), ('cancelled', 'Cancelled'), ('expired', 'Expired'),
]
TX_TYPES = [
    ('checkout', 'Checkout (one-time)'), ('renewal', 'Subscription Renewal'),
    ('retry', 'Payment Retry'), ('proration', 'Proration'), ('refund', 'Refund'), ('manual', 'Manual'),
]


class SaasPaymentTransaction(models.Model):
    _name = 'saas.payment.transaction'
    _description = 'Payment Transaction'
    _order = 'create_date desc'
    _rec_name = 'reference'

    reference = fields.Char(string='Reference', required=True, copy=False, index=True,
                           default=lambda self: self.env['ir.sequence'].next_by_code('saas.payment.tx'))
    tx_type = fields.Selection(selection=TX_TYPES, string='Type', default='checkout', required=True, index=True)
    status = fields.Selection(selection=TX_STATUS, string='Status', default='pending',
                              required=True, tracking=True, index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='restrict', index=True)
    subscription_id = fields.Many2one('saas.subscription', string='Subscription', ondelete='set null', index=True)
    invoice_id = fields.Many2one('saas.invoice', string='Invoice', ondelete='set null', index=True)
    gateway_id = fields.Many2one('saas.payment.gateway', string='Gateway', required=True, ondelete='restrict')
    payment_method_id = fields.Many2one('saas.payment.method', string='Payment Method', ondelete='set null')
    amount = fields.Float(string='Amount', digits=(10, 2), required=True)
    currency = fields.Char(string='Currency', default='SAR', required=True)
    amount_refunded = fields.Float(string='Refunded', digits=(10, 2), default=0.0)
    amount_net = fields.Float(string='Net Amount', compute='_compute_amount_net', store=True, digits=(10, 2))
    gateway_tx_ref = fields.Char(string='Gateway Transaction Ref', index=True, copy=False)
    gateway_order_id = fields.Char(string='Gateway Order ID', index=True)
    gateway_customer_id = fields.Char(string='Gateway Customer ID')
    checkout_url = fields.Char(string='Checkout URL')
    gateway_response = fields.Text(string='Gateway Raw Response')
    failure_reason = fields.Char(string='Failure Reason')
    error_code = fields.Char(string='Error Code')
    initiated_at = fields.Datetime(string='Initiated', default=fields.Datetime.now)
    confirmed_at = fields.Datetime(string='Confirmed At', readonly=True)
    expires_at = fields.Datetime(string='Expires At')

    _sql_constraints = [('gateway_tx_ref_unique', 'UNIQUE(gateway_tx_ref)',
                         'Gateway transaction reference must be unique.')]

    @api.depends('amount', 'amount_refunded')
    def _compute_amount_net(self):
        for rec in self:
            rec.amount_net = round(rec.amount - rec.amount_refunded, 2)

    def mark_processing(self):
        self.ensure_one()
        self.status = 'processing'

    def mark_success(self, gateway_response=None, confirmed_at=None):
        self.ensure_one()
        import json
        self.write({'status': 'success', 'confirmed_at': confirmed_at or fields.Datetime.now(),
                    'gateway_response': json.dumps(gateway_response or {}, default=str)[:10000]})

    def mark_failed(self, reason=None, code=None, gateway_response=None):
        self.ensure_one()
        import json
        self.write({'status': 'failed', 'failure_reason': reason or 'Payment failed',
                    'error_code': code or '', 'gateway_response': json.dumps(gateway_response or {}, default=str)[:10000]})

    def mark_refunded(self, refund_amount=None):
        self.ensure_one()
        self.write({'status': 'refunded', 'amount_refunded': refund_amount or self.amount})

    def unlink(self):
        if any(r.status in ('success', 'refunded') for r in self):
            raise UserError('Successful or refunded transactions cannot be deleted.')
        return super().unlink()
