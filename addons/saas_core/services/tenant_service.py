from odoo import _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class TenantService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_core.repositories.tenant_repository import TenantRepository
        from odoo.addons.saas_core.services.event_bus_service import EventBusService
        from odoo.addons.saas_core.services.audit_service import AuditService
        self.repo = TenantRepository(env)
        self.events = EventBusService(env)
        self.audit = AuditService(env)

    def create_lead(self, subdomain, customer_name, customer_email, plan_id,
                    lead_source='website', referral_code=None, coupon_code=None,
                    phone=None, company_name=None, country=None):
        if self.repo.find_by_subdomain(subdomain):
            raise ValidationError(_('Subdomain "%s" is already taken.', subdomain))
        plan = self.env['saas.plan'].browse(plan_id)
        if not plan.exists() or not plan.active:
            raise ValidationError(_('Invalid or inactive plan.'))
        tenant = self.env['saas.tenant'].create({
            'name': customer_name, 'customer_name': customer_name,
            'customer_email': customer_email, 'subdomain': subdomain,
            'plan_id': plan_id, 'state': 'lead', 'lead_source': lead_source,
            'referral_code': referral_code, 'coupon_code': coupon_code,
            'phone': phone, 'company_name': company_name,
            # Country chosen at signup — drives localization + company setup.
            'customer_country': (country or 'SA').upper()[:2],
            # Carry the edition over from the chosen plan so the provisioner
            # routes correctly even if the plan is unlinked later.
            'edition': plan.edition or 'community',
        })
        self.events.publish('tenant.lead.created', payload={
            'tenant_id': tenant.id, 'subdomain': subdomain, 'email': customer_email,
            'plan': plan.code, 'lead_source': lead_source}, tenant_id=tenant.id)
        _logger.info('TenantService: lead created %s (%s)', subdomain, customer_email)
        return tenant

    def provision_tenant(self, tenant):
        if tenant.state not in ('lead', 'trial'):
            raise UserError(_('Tenant must be in lead or trial state. Current: %s', tenant.state))
        return tenant.action_provision()

    def handle_payment_success(self, tenant, amount, gateway, tx_id):
        self.audit.log_payment(tenant, amount, 'success', gateway)
        if tenant.state in ('pending_payment', 'grace_period', 'suspended', 'trial'):
            tenant.action_activate()
        self.events.publish('payment.received', payload={
            'tenant_id': tenant.id, 'amount': amount, 'gateway': gateway, 'tx_id': tx_id},
            tenant_id=tenant.id)

    def handle_payment_failure(self, tenant, gateway, error):
        self.audit.log_payment(tenant, 0, 'failed', gateway)
        if tenant.state == 'active':
            tenant.action_start_grace_period()
        elif tenant.state == 'grace_period':
            if tenant.payment_retry_count >= 3:
                tenant.action_suspend()
            else:
                tenant.write({'payment_retry_count': tenant.payment_retry_count + 1})
        self.events.publish('payment.failed', payload={
            'tenant_id': tenant.id, 'gateway': gateway, 'error': error,
            'retry': tenant.payment_retry_count}, tenant_id=tenant.id)

    def get_platform_stats(self):
        counts = self.repo.count_by_state()
        return {'total_tenants': sum(counts.values()), 'active_tenants': counts.get('active', 0),
                'trial_tenants': counts.get('trial', 0),
                'new_this_month': self.repo.count_new_this_month(), 'by_state': counts}
