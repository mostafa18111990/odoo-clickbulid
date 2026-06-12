from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class CommissionService:
    def __init__(self, env):
        self.env = env

    def accrue_commission(self, payload):
        tenant_id = payload.get('tenant_id')
        amount = payload.get('amount', 0)
        if not tenant_id or amount <= 0:
            return
        tenant = self.env['saas.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant or not tenant.reseller_id:
            return
        reseller = tenant.reseller_id
        if reseller.state != 'active':
            return
        commission = reseller.calculate_commission(amount)
        if commission <= 0:
            return
        self.env['saas.reseller.commission'].sudo().create({
            'reseller_id': reseller.id, 'tenant_id': tenant.id, 'payment_amount': amount,
            'commission_rate': reseller.commission_rate, 'amount': commission,
            'currency': payload.get('currency', 'SAR'),
            'gateway_tx_id': payload.get('gateway_tx_id', ''), 'state': 'accrued'})
        _logger.info('Commission accrued: %s SAR for %s (customer %s)',
                     commission, reseller.name, tenant.subdomain)

    def generate_payout(self, reseller, period_start=None, period_end=None):
        domain = [('reseller_id', '=', reseller.id), ('state', '=', 'accrued'),
                  ('payout_id', '=', False)]
        if period_start:
            domain.append(('accrued_date', '>=', period_start))
        if period_end:
            domain.append(('accrued_date', '<=', period_end))
        commissions = self.env['saas.reseller.commission'].search(domain)
        if not commissions:
            return None
        total = sum(commissions.mapped('amount'))
        payout = self.env['saas.reseller.payout'].create({
            'reseller_id': reseller.id, 'amount': round(total, 2),
            'currency': reseller.currency, 'period_start': period_start,
            'period_end': period_end, 'state': 'draft'})
        commissions.write({'payout_id': payout.id})
        return payout

    def cron_monthly_payouts(self):
        from datetime import date
        today = date.today()
        if today.month == 1:
            ps = date(today.year - 1, 12, 1)
            pe = date(today.year, 1, 1)
        else:
            ps = date(today.year, today.month - 1, 1)
            pe = date(today.year, today.month, 1)
        for reseller in self.env['saas.reseller'].search([('state', '=', 'active')]):
            try:
                self.generate_payout(reseller, ps, pe)
            except Exception as e:
                _logger.error('Payout generation failed for %s: %s', reseller.name, e)
