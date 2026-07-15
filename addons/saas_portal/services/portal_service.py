from odoo import fields, _
from odoo.exceptions import UserError, AccessError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class PortalService:
    def __init__(self, env):
        self.env = env

    def get_dashboard_data(self, tenant):
        sub = tenant.current_subscription_id
        plan = tenant.plan_id
        users_used = tenant.users_count or 0
        users_max = tenant.effective_max_users()
        storage_used_mb = tenant.total_storage_mb or tenant.disk_usage_mb or 0
        storage_max_mb = plan.max_storage_mb if plan else 0
        recent_invoices = self.env['saas.invoice'].search([('tenant_id', '=', tenant.id)],
                                                          order='invoice_date desc', limit=5)
        return {
            'tenant': {'name': tenant.name, 'subdomain': tenant.subdomain, 'url': tenant.get_sso_url(),
                       'state': tenant.state,
                       'state_label': dict(tenant._fields['state'].selection).get(tenant.state, tenant.state)},
            'subscription': {'plan_name': plan.name if plan else 'N/A', 'status': sub.status if sub else 'none',
                             'billing_cycle': sub.billing_cycle if sub else '',
                             'amount': sub.total_amount if sub else 0, 'currency': sub.currency if sub else 'SAR',
                             'next_renewal': sub.next_renewal_date if sub else None,
                             'days_to_renewal': sub.days_to_renewal if sub else 0,
                             'credit_balance': sub.credit_balance if sub else 0,
                             'trial_days_left': tenant.trial_days_left, 'is_trial': tenant.state == 'trial'},
            'usage': {'users_used': users_used, 'users_max': users_max,
                      'users_pct': round(users_used / users_max * 100) if users_max else 0,
                      'storage_used_gb': round(storage_used_mb / 1024, 2),
                      'storage_max_gb': round(storage_max_mb / 1024, 2),
                      'storage_pct': round(storage_used_mb / storage_max_mb * 100) if storage_max_mb else 0},
            'invoices': [{'id': i.id, 'number': i.number, 'date': i.invoice_date, 'amount': i.amount_total,
                          'currency': i.currency, 'status': i.status} for i in recent_invoices],
        }

    def get_subscription_data(self, tenant):
        sub = tenant.current_subscription_id
        if not sub:
            return {'has_subscription': False}
        return {'has_subscription': True, 'plan_name': sub.plan_id.name, 'plan_code': sub.plan_id.code,
                'status': sub.status, 'billing_cycle': sub.billing_cycle, 'base_amount': sub.base_amount,
                'discount_amount': sub.discount_amount, 'total_amount': sub.total_amount, 'currency': sub.currency,
                'current_period_start': sub.current_period_start, 'current_period_end': sub.current_period_end,
                'next_renewal_date': sub.next_renewal_date, 'days_to_renewal': sub.days_to_renewal,
                'credit_balance': sub.credit_balance, 'cancel_at_period_end': sub.cancel_at_period_end,
                'coupon_code': sub.coupon_code}

    def get_available_plans(self, tenant):
        current_plan = tenant.plan_id
        current_price = current_plan.monthly_price if current_plan else 0
        plans = self.env['saas.plan'].search([('active', '=', True)], order='monthly_price asc')
        result = []
        for plan in plans:
            result.append({'id': plan.id, 'name': plan.name, 'code': plan.code,
                           'monthly_price': plan.monthly_price, 'yearly_price': plan.get_effective_yearly_price(),
                           'max_users': plan.max_users,
                           'max_storage_gb': round(plan.max_storage_mb / 1024, 1) if plan.max_storage_mb else 0,
                           'max_companies': plan.max_companies, 'is_popular': plan.is_popular,
                           'is_recommended': plan.is_recommended, 'is_current': plan == current_plan,
                           'is_upgrade': plan.monthly_price > current_price,
                           'is_downgrade': plan.monthly_price < current_price,
                           'features': plan.features.split('\n') if plan.features else []})
        return result

    def request_upgrade(self, tenant, new_plan_id):
        sub = tenant.current_subscription_id
        if not sub:
            raise UserError(_('No active subscription found.'))
        new_plan = self.env['saas.plan'].browse(new_plan_id).exists()
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        svc = SubscriptionService(self.env)
        change = svc.upgrade(sub, new_plan, immediate=True)
        if change.proration_amount > 0:
            from odoo.addons.saas_billing.services.invoice_service import InvoiceService
            inv = InvoiceService(self.env).generate_proration_invoice(change.id)
            if inv:
                inv.action_confirm()
                from odoo.addons.saas_payment.services.payment_service import PaymentService
                checkout = PaymentService(self.env).initiate_checkout(tenant=tenant, amount=inv.amount_total,
                    currency=inv.currency, invoice_id=inv.id, subscription_id=sub.id, tx_type='proration')
                return {'checkout_url': checkout.get('checkout_url'), 'requires_payment': True}
        return {'requires_payment': False, 'message': _('Plan upgraded successfully.')}

    def request_downgrade(self, tenant, new_plan_id):
        sub = tenant.current_subscription_id
        if not sub:
            raise UserError(_('No active subscription found.'))
        new_plan = self.env['saas.plan'].browse(new_plan_id).exists()
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        SubscriptionService(self.env).downgrade(sub, new_plan, immediate=False)
        return {'message': _('Downgrade scheduled for the end of your current period.')}

    def request_cancel(self, tenant, reason_code=None, note=None):
        sub = tenant.current_subscription_id
        if not sub:
            raise UserError(_('No active subscription found.'))
        reason = None
        if reason_code:
            reason = self.env['saas.cancellation.reason'].search([('code', '=', reason_code)], limit=1)
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        SubscriptionService(self.env).cancel(sub, at_period_end=True,
            reason_id=reason.id if reason else None, note=note)
        return {'message': _('Your subscription will be cancelled at the end of the current period.')}

    def request_cycle_change(self, tenant, new_cycle):
        sub = tenant.current_subscription_id
        if not sub:
            raise UserError(_('No active subscription found.'))
        from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
        SubscriptionService(self.env).change_cycle(sub, new_cycle)
        return {'message': _('Billing cycle updated.')}

    def get_invoices(self, tenant, limit=50):
        invoices = self.env['saas.invoice'].search([('tenant_id', '=', tenant.id), ('status', '!=', 'draft')],
                                                   order='invoice_date desc', limit=limit)
        return [{'id': i.id, 'number': i.number, 'date': i.invoice_date, 'due_date': i.due_date,
                 'amount_total': i.amount_total, 'amount_tax': i.amount_tax, 'currency': i.currency,
                 'status': i.status, 'has_pdf': bool(i.pdf_attachment_id)} for i in invoices]

    def get_invoice(self, tenant, invoice_id):
        invoice = self.env['saas.invoice'].search([('id', '=', invoice_id), ('tenant_id', '=', tenant.id)], limit=1)
        if not invoice:
            raise AccessError(_('Invoice not found or access denied.'))
        return invoice

    def get_usage_data(self, tenant):
        plan = tenant.plan_id
        return {'users': {'used': tenant.users_count or 0,
                          'max': tenant.effective_max_users() or 'Unlimited'},
                'storage': {'used_gb': round((tenant.total_storage_mb or tenant.disk_usage_mb or 0) / 1024, 2),
                            'max_gb': round((plan.max_storage_mb or 0) / 1024, 2) if plan else 0}}
