from odoo import models, fields, api, _
from odoo.exceptions import UserError

CN_STATUS = [('draft', 'Draft'), ('applied', 'Applied'), ('refunded', 'Refunded'), ('cancelled', 'Cancelled')]
CN_TYPES = [('full_credit', 'Full Credit'), ('partial', 'Partial Refund'), ('write_off', 'Write Off')]


class SaasCreditNote(models.Model):
    _name = 'saas.credit.note'
    _description = 'SaaS Credit Note'
    _order = 'create_date desc'
    _rec_name = 'number'

    number = fields.Char(string='Credit Note Number', readonly=True, copy=False, index=True, default='CN-Draft')
    status = fields.Selection(selection=CN_STATUS, string='Status', default='draft',
                              required=True, tracking=True, index=True)
    cn_type = fields.Selection(selection=CN_TYPES, string='Type', default='full_credit', required=True)
    invoice_id = fields.Many2one('saas.invoice', string='Original Invoice', required=True,
                                 ondelete='restrict', index=True)
    tenant_id = fields.Many2one('saas.tenant', related='invoice_id.tenant_id', store=True, index=True)
    subscription_id = fields.Many2one('saas.subscription', related='invoice_id.subscription_id', store=True)
    amount = fields.Float(string='Credit Amount', digits=(10, 2), required=True)
    currency = fields.Selection(related='invoice_id.currency', store=True, string='Currency')
    tax_amount = fields.Float(string='Tax Refunded', digits=(10, 2), default=0.0)
    total = fields.Float(string='Total', compute='_compute_total', store=True, digits=(10, 2))
    reason = fields.Text(string='Reason', required=True)
    cn_date = fields.Date(string='Credit Note Date', default=fields.Date.today, required=True)
    applied_date = fields.Date(string='Applied Date', readonly=True)
    gateway_refund_id = fields.Char(string='Gateway Refund ID')
    zatca_qr_code = fields.Text(string='ZATCA QR Code', readonly=True)

    @api.depends('amount', 'tax_amount')
    def _compute_total(self):
        for rec in self:
            rec.total = round(rec.amount + rec.tax_amount, 2)

    @api.constrains('amount', 'invoice_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError('Credit note amount must be positive.')
            if rec.amount > rec.invoice_id.amount_total:
                raise UserError(f'Credit amount ({rec.amount}) cannot exceed invoice total ({rec.invoice_id.amount_total}).')

    def action_apply(self):
        self.ensure_one()
        if self.status != 'draft':
            raise UserError(_('Only draft credit notes can be applied.'))
        self.number = self.env['ir.sequence'].next_by_code('saas.credit.note') or f'CN-{fields.Date.today().year}-MANUAL'
        sub = self.subscription_id
        if sub:
            sub.apply_credit(self.amount, f'Credit note {self.number}: {self.reason}')
        self.write({'status': 'applied', 'applied_date': fields.Date.today()})
        self.env['saas.event']._publish(event_type='payment.refunded', model='saas.credit.note',
            record_id=self.id, payload={'credit_note_id': self.id, 'invoice_id': self.invoice_id.id,
            'amount': self.amount, 'tenant_id': self.tenant_id.id}, tenant_id=self.tenant_id.id)

    def action_cancel(self):
        self.ensure_one()
        if self.status == 'applied':
            raise UserError(_('Cannot cancel an applied credit note.'))
        self.status = 'cancelled'

    def write(self, vals):
        for rec in self:
            if rec.status in ('applied', 'refunded') and set(vals.keys()) - {'status', 'gateway_refund_id'}:
                raise UserError(_('Applied credit notes are immutable.'))
        return super().write(vals)
