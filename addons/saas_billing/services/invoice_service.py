from odoo import fields, _
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)
PAYMENT_TERMS_DAYS = 7


class InvoiceService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_billing.services.tax_service import TaxService
        self.tax_svc = TaxService(env)

    def generate_renewal_invoice(self, subscription_id):
        sub = self.env['saas.subscription'].browse(subscription_id).exists()
        if not sub:
            return None
        existing = self.env['saas.invoice'].search([
            ('subscription_id', '=', sub.id), ('status', '=', 'draft'),
            ('invoice_type', '=', 'subscription')], limit=1)
        if existing:
            return existing
        tenant = sub.tenant_id
        config = self.env['saas.config']._get_config()
        tax_data = self.tax_svc.calculate_tax(sub.base_amount, tenant, 'subscription')
        invoice_date = date.today()
        due_date = invoice_date + timedelta(days=PAYMENT_TERMS_DAYS)
        period_end = sub.current_period_end or (invoice_date + timedelta(days=30))
        invoice = self.env['saas.invoice'].create({
            'invoice_type': 'subscription', 'status': 'draft', 'tenant_id': tenant.id,
            'subscription_id': sub.id, 'customer_name': tenant.customer_name or tenant.name,
            'customer_email': tenant.customer_email,
            'customer_country': getattr(tenant, 'customer_country', '') or '',
            'company_name': config.platform_name, 'company_vat': getattr(config, 'company_vat', '') or '',
            'company_address': f'{config.platform_name}\n{config.platform_domain}',
            'invoice_date': invoice_date, 'due_date': due_date,
            'period_start': sub.current_period_start or invoice_date, 'period_end': period_end,
            'currency': sub.currency, 'tax_rate_id': tax_data['tax_rate'].id if tax_data['tax_rate'] else False,
            'tax_rate_pct': tax_data['rate_pct'], 'payment_gateway': sub.payment_gateway})
        self._create_subscription_lines(invoice, sub, tax_data)
        self._create_overage_lines(invoice, sub)
        _logger.info('Generated renewal invoice for %s', tenant.subdomain)
        return invoice

    def _create_subscription_lines(self, invoice, sub, tax_data):
        plan = sub.plan_id
        cycle_label = 'Monthly' if sub.billing_cycle == 'monthly' else 'Annual'
        period_label = ''
        if sub.current_period_start and sub.current_period_end:
            period_label = f' ({sub.current_period_start.strftime("%d/%m/%Y")} - {sub.current_period_end.strftime("%d/%m/%Y")})'
        self.env['saas.invoice.line'].create({
            'invoice_id': invoice.id, 'sequence': 10, 'line_type': 'subscription',
            'name': f'{plan.name} Plan - {cycle_label} Subscription{period_label}',
            'name_ar': f'خطة {plan.name} - اشتراك {"شهري" if sub.billing_cycle == "monthly" else "سنوي"}',
            'quantity': 1, 'unit_price': sub.base_amount,
            'period_start': sub.current_period_start, 'period_end': sub.current_period_end})
        if sub.discount_amount > 0:
            self.env['saas.invoice.line'].create({
                'invoice_id': invoice.id, 'sequence': 20, 'line_type': 'discount',
                'name': f'Discount ({sub.coupon_code or "applied"})', 'quantity': 1,
                'unit_price': -sub.discount_amount})
        if tax_data['tax_amount'] > 0:
            label_en, label_ar = self.tax_svc.get_invoice_tax_label(invoice.tenant_id)
            self.env['saas.invoice.line'].create({
                'invoice_id': invoice.id, 'sequence': 90, 'line_type': 'tax', 'name': label_en,
                'name_ar': label_ar, 'quantity': 1, 'unit_price': 0,
                'tax_rate_id': tax_data['tax_rate'].id if tax_data['tax_rate'] else False,
                'tax_amount': tax_data['tax_amount']})

    def _create_overage_lines(self, invoice, sub):
        for line in sub.line_ids.filtered(lambda l: not l.billed):
            tax_amount = self.tax_svc.calculate_tax(line.amount, sub.tenant_id, 'overage')['tax_amount']
            self.env['saas.invoice.line'].create({
                'invoice_id': invoice.id, 'sequence': 50,
                'line_type': 'overage_user' if 'user' in line.line_type else 'overage_storage',
                'name': line.name, 'quantity': line.quantity, 'unit_price': line.unit_price,
                'period_start': line.period_start, 'period_end': line.period_end,
                'tax_amount': tax_amount, 'subscription_line_id': line.id})
            line.billed = True

    def generate_proration_invoice(self, plan_change_id):
        change = self.env['saas.plan.change'].browse(plan_change_id).exists()
        if not change or change.proration_amount <= 0:
            return None
        sub = change.subscription_id
        tenant = change.tenant_id
        tax_data = self.tax_svc.calculate_tax(change.proration_amount, tenant, 'subscription')
        invoice = self.env['saas.invoice'].create({
            'invoice_type': 'proration', 'status': 'draft', 'tenant_id': tenant.id,
            'subscription_id': sub.id, 'customer_name': tenant.customer_name or tenant.name,
            'customer_email': tenant.customer_email, 'invoice_date': date.today(),
            'due_date': date.today() + timedelta(days=PAYMENT_TERMS_DAYS), 'currency': sub.currency,
            'tax_rate_id': tax_data['tax_rate'].id if tax_data['tax_rate'] else False,
            'tax_rate_pct': tax_data['rate_pct']})
        self.env['saas.invoice.line'].create({
            'invoice_id': invoice.id, 'line_type': 'proration',
            'name': f'Plan Upgrade: {change.from_plan_id.name} -> {change.to_plan_id.name} ({change.days_remaining} days)',
            'quantity': 1, 'unit_price': change.proration_amount, 'tax_amount': tax_data['tax_amount']})
        return invoice

    def generate_credit_note(self, invoice_id, amount, reason, cn_type='partial'):
        invoice = self.env['saas.invoice'].browse(invoice_id).exists()
        if not invoice:
            raise UserError(f'Invoice {invoice_id} not found.')
        tax_refund = round(amount * invoice.tax_rate_pct / 100, 2) if invoice.tax_rate_pct else 0
        cn = self.env['saas.credit.note'].create({'invoice_id': invoice.id, 'cn_type': cn_type,
            'amount': amount, 'tax_amount': tax_refund, 'reason': reason, 'cn_date': date.today()})
        cn.action_apply()
        return cn

    def on_payment_received(self, subscription_id, tx_id, amount):
        invoice = self.env['saas.invoice'].search([
            ('subscription_id', '=', subscription_id),
            ('status', 'in', ('draft', 'sent', 'overdue'))], order='invoice_date desc', limit=1)
        if invoice:
            if invoice.status == 'draft':
                invoice.action_confirm()
            invoice.action_mark_paid(amount=amount, tx_id=tx_id)
        else:
            _logger.warning('on_payment_received: no pending invoice for sub %d', subscription_id)
