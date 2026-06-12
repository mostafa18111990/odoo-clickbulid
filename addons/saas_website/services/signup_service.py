from odoo import _
from odoo.exceptions import ValidationError, UserError
import re
import logging

_logger = logging.getLogger(__name__)

RESERVED_SUBDOMAINS = {
    'www', 'api', 'admin', 'mail', 'ftp', 'ssh', 'ns1', 'ns2', 'app', 'dashboard',
    'portal', 'support', 'help', 'blog', 'clickbuild', 'static', 'cdn', 'assets',
    'odoo', 'test', 'demo', 'staging', 'dev', 'mx', 'smtp', 'pop', 'imap',
    'webmail', 'secure', 'vpn', 'status', 'docs',
}
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
SUBDOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$')


class SignupService:
    def __init__(self, env):
        self.env = env

    def check_subdomain(self, subdomain):
        subdomain = (subdomain or '').lower().strip()
        if len(subdomain) < 3:
            return {'available': False, 'reason': {'ar': 'يجب 3 أحرف على الأقل', 'en': 'Min 3 characters'}}
        if subdomain in RESERVED_SUBDOMAINS:
            return {'available': False, 'reason': {'ar': 'الاسم محجوز', 'en': 'Reserved'}}
        if not SUBDOMAIN_RE.match(subdomain):
            return {'available': False, 'reason': {'ar': 'أحرف إنجليزية وأرقام فقط', 'en': 'Invalid characters'}}
        existing = self.env['saas.tenant'].sudo().search([
            ('subdomain', '=', subdomain), ('state', '!=', 'deleted')], limit=1)
        if existing:
            return {'available': False, 'reason': {'ar': 'محجوز مسبقاً', 'en': 'Already taken'}}
        config = self.env['saas.config'].sudo()._get_config()
        return {'available': True, 'url': f'https://{subdomain}.{config.platform_domain}'}

    def validate_signup(self, data):
        errors = []
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        subdomain = (data.get('subdomain') or '').strip().lower()
        if len(name) < 2:
            errors.append(_('Please enter your name.'))
        if not EMAIL_RE.match(email):
            errors.append(_('Please enter a valid email address.'))
        check = self.check_subdomain(subdomain)
        if not check.get('available'):
            errors.append(check.get('reason', {}).get('en', 'Invalid subdomain.'))
        plan_id = data.get('plan_id')
        if plan_id:
            plan = self.env['saas.plan'].sudo().browse(int(plan_id)).exists()
            if not plan or not plan.active:
                errors.append(_('Selected plan is not available.'))
        return errors

    def register(self, data):
        errors = self.validate_signup(data)
        if errors:
            return {'success': False, 'errors': errors}
        name = data['name'].strip()
        email = data['email'].strip().lower()
        subdomain = data['subdomain'].strip().lower()
        company = (data.get('company') or '').strip()
        phone = (data.get('phone') or '').strip()
        country = (data.get('country') or 'SA').strip()
        plan_id = int(data['plan_id']) if data.get('plan_id') else None
        if not plan_id:
            plan = self.env['saas.plan'].sudo().search([('active', '=', True)], order='monthly_price asc', limit=1)
            plan_id = plan.id if plan else None
        else:
            plan = self.env['saas.plan'].sudo().browse(plan_id)
        if not plan_id:
            return {'success': False, 'errors': [_('No plans available.')]}
        from odoo.addons.saas_core.services.tenant_service import TenantService
        svc = TenantService(self.env(su=True))
        try:
            tenant = svc.create_lead(subdomain=subdomain, customer_name=name, customer_email=email,
                plan_id=plan_id, lead_source='website', phone=phone, company_name=company,
                coupon_code=data.get('coupon_code'), referral_code=data.get('referral_code'))
            # Country is preserved via the subscription currency derived below.
            # (saas.tenant has no customer_country field in the current base module.)
            provision_result = tenant.sudo().action_provision()
            admin_password = (provision_result or {}).get('admin_password_one_time')
            if 'saas.subscription' in self.env:
                from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
                currency = self._currency_for_country(country)
                SubscriptionService(self.env(su=True)).create_trial(tenant, plan, 'monthly', currency)
            self._link_website_lead(email, tenant)
            # Send the welcome email with credentials (best-effort —
            # never block signup if SMTP isn't configured).
            self._send_welcome_email(tenant, admin_password)
            config = self.env['saas.config'].sudo()._get_config()
            return {'success': True, 'tenant_id': tenant.id, 'subdomain': subdomain,
                    'url': f'https://{subdomain}.{config.platform_domain}',
                    'admin_email': email,
                    'admin_password_one_time': admin_password,
                    'message': _('Your workspace is being created! Check your email.'),
                    'redirect': f'/get-started/success?tenant={subdomain}'}
        except (ValidationError, UserError) as e:
            return {'success': False, 'errors': [str(e)]}
        except Exception as e:
            _logger.error('Signup failed for %s: %s', subdomain, e)
            return {'success': False, 'errors': [_('Registration failed. Please try again.')]}

    def _send_welcome_email(self, tenant, admin_password):
        """Send signup welcome email with login credentials.

        Failures are logged but never raised — signup must succeed even when
        SMTP is unavailable (the success page still shows the password).
        """
        if not admin_password:
            return  # nothing to send if provisioning didn't return a password
        try:
            template = self.env.ref('saas_website.email_template_signup_welcome',
                                    raise_if_not_found=False)
            if not template:
                _logger.warning('Welcome email template not found, skipping')
                return
            template.with_context(admin_password=admin_password).send_mail(
                tenant.id, force_send=False, email_layout_xmlid=None)
            _logger.info('Welcome email queued for tenant %s -> %s',
                         tenant.subdomain, tenant.customer_email)
        except Exception as e:
            _logger.warning('Welcome email failed for %s: %s — '
                            'password still shown on success page.',
                            tenant.subdomain, e)

    def _currency_for_country(self, country):
        return {'SA': 'SAR', 'AE': 'AED', 'EG': 'EGP', 'KW': 'KWD'}.get(country[:2].upper() if country else '', 'SAR')

    def _link_website_lead(self, email, tenant):
        lead = self.env['saas.website.lead'].sudo().search([
            ('email', '=', email), ('state', '!=', 'converted')], limit=1)
        if lead:
            lead.action_mark_converted(tenant)

    def capture_lead(self, data):
        try:
            lead = self.env['saas.website.lead'].sudo().create({
                'name': data.get('name', 'Anonymous'), 'email': data.get('email', ''),
                'phone': data.get('phone', ''), 'company': data.get('company', ''),
                'message': data.get('message', ''), 'source': data.get('source', 'contact_form'),
                'country': data.get('country', ''), 'language': data.get('language', 'ar'),
                'newsletter_opt_in': data.get('newsletter', False)})
            return {'success': True, 'lead_id': lead.id}
        except Exception as e:
            _logger.error('Lead capture failed: %s', e)
            return {'success': False, 'error': str(e)}
