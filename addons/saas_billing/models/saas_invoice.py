from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date
import logging

_logger = logging.getLogger(__name__)

INVOICE_STATUS = [
    ('draft', 'Draft'), ('sent', 'Sent'), ('paid', 'Paid'),
    ('overdue', 'Overdue'), ('voided', 'Voided'),
]
INVOICE_TYPES = [
    ('subscription', 'Subscription Invoice'), ('proration', 'Proration Invoice'),
    ('usage', 'Usage / Overage Invoice'), ('manual', 'Manual Invoice'),
]


class SaasInvoice(models.Model):
    _name = 'saas.invoice'
    _description = 'SaaS Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'invoice_date desc, number desc'
    _rec_name = 'number'

    number = fields.Char(string='Invoice Number', readonly=True, copy=False, index=True, default='Draft')
    invoice_type = fields.Selection(selection=INVOICE_TYPES, string='Type', default='subscription',
                                    required=True, index=True)
    status = fields.Selection(selection=INVOICE_STATUS, string='Status', default='draft',
                              required=True, tracking=True, index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='restrict', index=True)
    subscription_id = fields.Many2one('saas.subscription', string='Subscription', ondelete='set null', index=True)
    customer_name = fields.Char(string='Customer Name', required=True)
    customer_email = fields.Char(string='Customer Email')
    customer_address = fields.Text(string='Customer Address')
    customer_vat = fields.Char(string='Customer VAT Number')
    customer_country = fields.Char(string='Customer Country')
    company_name = fields.Char(string='Company Name', default='ClickBuild')
    company_vat = fields.Char(string='Company VAT Number')
    company_address = fields.Text(string='Company Address')
    company_cr = fields.Char(string='Commercial Registration')
    invoice_date = fields.Date(string='Invoice Date', required=True, default=fields.Date.today, index=True)
    due_date = fields.Date(string='Due Date', required=True, index=True)
    period_start = fields.Date(string='Billing Period Start')
    period_end = fields.Date(string='Billing Period End')
    paid_date = fields.Date(string='Paid Date', readonly=True)
    currency = fields.Selection(
        selection=[('SAR', 'SAR'), ('AED', 'AED'), ('USD', 'USD'), ('EGP', 'EGP'), ('KWD', 'KWD')],
        string='Currency', default='SAR', required=True)
    amount_subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True, digits=(10, 2))
    amount_tax = fields.Float(string='Tax Total', compute='_compute_tax_total', store=True, digits=(10, 2))
    amount_total = fields.Float(string='Total', compute='_compute_total', store=True, digits=(10, 2), tracking=True)
    amount_paid = fields.Float(string='Amount Paid', digits=(10, 2), default=0.0, readonly=True)
    amount_due = fields.Float(string='Amount Due', compute='_compute_amount_due', store=True, digits=(10, 2))
    tax_rate_id = fields.Many2one('saas.tax.rate', string='Tax Rate Applied')
    tax_rate_pct = fields.Float(string='Tax Rate %', digits=(5, 2), default=0.0)
    zatca_qr_code = fields.Text(string='ZATCA QR Code (Base64)', readonly=True)
    zatca_invoice_hash = fields.Char(string='Invoice Hash', readonly=True)
    payment_gateway = fields.Char(string='Payment Gateway')
    gateway_tx_id = fields.Char(string='Transaction ID', index=True, copy=False)
    gateway_invoice_id = fields.Char(string='Gateway Invoice ID', index=True)
    line_ids = fields.One2many('saas.invoice.line', 'invoice_id', string='Invoice Lines')
    credit_note_ids = fields.One2many('saas.credit.note', 'invoice_id', string='Credit Notes')
    credit_note_count = fields.Integer(string='Credit Notes', compute='_compute_credit_note_count')
    pdf_attachment_id = fields.Many2one('ir.attachment', string='PDF Invoice', readonly=True, copy=False)
    internal_note = fields.Text(string='Internal Note')
    customer_note = fields.Text(string='Customer Note')

    @api.depends('line_ids.subtotal', 'line_ids.line_type')
    def _compute_subtotal(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: l.line_type not in ('tax', 'credit', 'discount'))
            rec.amount_subtotal = round(sum(lines.mapped('subtotal')), 2)

    @api.depends('line_ids.tax_amount')
    def _compute_tax_total(self):
        for rec in self:
            rec.amount_tax = round(sum(rec.line_ids.mapped('tax_amount')), 2)

    @api.depends('amount_subtotal', 'amount_tax')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = round(rec.amount_subtotal + rec.amount_tax, 2)

    @api.depends('amount_total', 'amount_paid')
    def _compute_amount_due(self):
        for rec in self:
            rec.amount_due = max(0, round(rec.amount_total - rec.amount_paid, 2))

    @api.depends('credit_note_ids')
    def _compute_credit_note_count(self):
        for rec in self:
            rec.credit_note_count = len(rec.credit_note_ids)

    def _assign_number(self):
        self.ensure_one()
        if self.number == 'Draft' or not self.number:
            self.number = self.env['ir.sequence'].next_by_code('saas.invoice') or f'INV-{date.today().year}-MANUAL'

    def action_confirm(self):
        for rec in self:
            if rec.status != 'draft':
                raise UserError(_('Only draft invoices can be confirmed.'))
            rec._assign_number()
            rec._generate_zatca_qr()
            rec.status = 'sent'
            rec._generate_pdf()
        for rec in self:
            self.env['saas.event']._publish(event_type='invoice.generated', model='saas.invoice',
                record_id=rec.id, payload={'invoice_id': rec.id, 'number': rec.number,
                'amount': rec.amount_total, 'currency': rec.currency, 'tenant_id': rec.tenant_id.id},
                tenant_id=rec.tenant_id.id)

    def action_mark_paid(self, amount=None, tx_id=None, paid_date=None):
        self.ensure_one()
        if self.status == 'voided':
            raise UserError(_('Cannot mark a voided invoice as paid.'))
        self.write({'status': 'paid', 'amount_paid': amount or self.amount_total,
                    'paid_date': paid_date or fields.Date.today(), 'gateway_tx_id': tx_id or self.gateway_tx_id})
        self.env['saas.event']._publish(event_type='invoice.paid', model='saas.invoice', record_id=self.id,
            payload={'invoice_id': self.id, 'number': self.number, 'amount': self.amount_paid,
            'tx_id': tx_id, 'tenant_id': self.tenant_id.id}, tenant_id=self.tenant_id.id)

    def action_void(self, reason=None):
        self.ensure_one()
        if self.status == 'paid':
            raise UserError(_('Cannot void a paid invoice. Create a credit note instead.'))
        if self.status == 'voided':
            raise UserError(_('Invoice is already voided.'))
        self.status = 'voided'
        self.message_post(body=f'Invoice voided. Reason: {reason or "Not specified"}')

    def action_send_reminder(self):
        self.ensure_one()
        if self.status not in ('sent', 'overdue'):
            raise UserError(_('Can only send reminders for sent or overdue invoices.'))
        self.env['saas.event']._publish(event_type='invoice.overdue', model='saas.invoice', record_id=self.id,
            payload={'invoice_id': self.id, 'number': self.number, 'amount_due': self.amount_due,
            'due_date': str(self.due_date), 'tenant_id': self.tenant_id.id}, tenant_id=self.tenant_id.id)

    def action_print_invoice(self):
        self.ensure_one()
        return self.env.ref('saas_billing.action_report_saas_invoice').report_action(self)

    def action_view_credit_notes(self):
        self.ensure_one()
        return {'name': _('Credit Notes'), 'type': 'ir.actions.act_window',
                'res_model': 'saas.credit.note', 'view_mode': 'list,form',
                'domain': [('invoice_id', '=', self.id)]}

    def _generate_zatca_qr(self):
        if self.customer_country not in ('SA', 'Saudi Arabia'):
            return
        from odoo.addons.saas_billing.services.zatca_service import ZatcaService
        config = self.env['saas.config']._get_config()
        self.zatca_qr_code = ZatcaService.generate_qr(
            seller_name=config.platform_name, vat_number=self.company_vat or '',
            timestamp=fields.Datetime.now().isoformat(), total=self.amount_total, vat_amount=self.amount_tax)

    def _generate_pdf(self):
        try:
            report = self.env.ref('saas_billing.action_report_saas_invoice')
            pdf_content, _dummy = report._render_qweb_pdf([self.id])
            attachment = self.env['ir.attachment'].create({
                'name': f'Invoice-{self.number}.pdf', 'type': 'binary', 'datas': pdf_content,
                'res_model': 'saas.invoice', 'res_id': self.id, 'mimetype': 'application/pdf'})
            self.pdf_attachment_id = attachment.id
        except Exception as e:
            _logger.error('PDF generation failed for invoice %s: %s', self.number, e)

    @api.model
    def cron_mark_overdue(self):
        today = date.today()
        overdue = self.search([('status', '=', 'sent'), ('due_date', '<', today)])
        overdue.write({'status': 'overdue'})
        for inv in overdue:
            inv.action_send_reminder()
        _logger.info('Marked %d invoices as overdue', len(overdue))
