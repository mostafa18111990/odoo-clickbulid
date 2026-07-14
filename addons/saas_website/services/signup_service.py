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
        # Validate the sector against the tenant field's own selection so the
        # form, the model and the provisioner can never drift apart.
        allowed_industries = dict(self.env['saas.tenant']._fields['industry'].selection)
        industry = (data.get('industry') or '').strip().lower()
        if industry not in allowed_industries:
            industry = 'other' if data.get('industry') else None
        # Seats chosen at signup (per-user pricing plans). Clamped to the
        # plan's ceiling further below once the plan is resolved.
        try:
            user_count = max(0, min(int(data.get('user_count') or 0), 500))
        except (TypeError, ValueError):
            user_count = 0
        edition = data.get('edition') if data.get('edition') in ('community', 'enterprise') else None
        billing_cycle = data.get('billing_cycle') if data.get('billing_cycle') in ('monthly', 'yearly') else 'monthly'
        submitted_plan = self.env['saas.plan'].sudo().browse(int(data['plan_id'])).exists() if data.get('plan_id') else None
        edition = edition or (submitted_plan.edition if submitted_plan else 'community')
        plan = self.env['saas.plan'].tier_plan_for(edition, user_count or 1)
        plan_id = plan.id if plan else None
        if not plan_id:
            return {'success': False, 'errors': [_('No plans available.')]}
        from odoo.addons.saas_core.services.tenant_service import TenantService
        svc = TenantService(self.env(su=True))
        try:
            # Clamp seats to the plan ceiling (0 = plan default).
            if user_count and plan and plan.max_users:
                user_count = min(user_count, plan.max_users)
            tenant = svc.create_lead(subdomain=subdomain, customer_name=name, customer_email=email,
                plan_id=plan_id, lead_source='website', phone=phone, company_name=company,
                coupon_code=data.get('coupon_code'), referral_code=data.get('referral_code'),
                country=country, industry=industry, user_count=user_count)
            # Country also drives the subscription currency derived below, and is
            # now persisted on the tenant so the provisioner installs the matching
            # localization (e.g. Saudi l10n_sa + ZATCA e-invoicing) and sets the
            # company's country/currency.
            provision_result = tenant.sudo().action_provision()
            admin_password = (provision_result or {}).get('admin_password_one_time')
            if 'saas.subscription' in self.env:
                from odoo.addons.saas_subscription.services.subscription_service import SubscriptionService
                currency = self._currency_for_country(country)
                SubscriptionService(self.env(su=True)).create_trial(tenant, plan, billing_cycle, currency)
            self._link_website_lead(email, tenant)
            # Send the welcome email with credentials (best-effort —
            # never block signup if SMTP isn't configured).
            self._send_welcome_email(tenant, admin_password)
            config = self.env['saas.config'].sudo()._get_config()
            return {'success': True, 'tenant_id': tenant.id, 'subdomain': subdomain,
                    'url': f'https://{subdomain}.{config.platform_domain}',
                    'admin_email': email,
                    'admin_password_one_time': admin_password,
                    'message': _('Your business platform is being created! Check your email.'),
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
            # Render the template, then send DIRECTLY via the configured
            # Hostinger mailbox. We bypass Odoo's mail-server From-rewrite
            # (it rewrites From to noreply@<catchall> which Hostinger rejects
            # because the sender must equal the authenticated mailbox).
            tpl = template.with_context(admin_password=admin_password)
            subject = tpl._render_field('subject', [tenant.id])[tenant.id]
            body = tpl._render_field('body_html', [tenant.id])[tenant.id]
            server = self.env['ir.mail_server'].sudo().search([], order='sequence', limit=1)
            if not server or not server.smtp_user:
                _logger.warning('No outgoing mail server configured, skipping welcome email')
                return
            self._smtp_send(server, tenant.customer_email, subject, body)
            _logger.info('Welcome email sent to %s (%s)',
                         tenant.customer_email, tenant.subdomain)
        except Exception as e:
            _logger.warning('Welcome email failed for %s: %s — '
                            'password still shown on success page.',
                            tenant.subdomain, e)

    def _smtp_send(self, server, to_addr, subject, html_body):
        """Send one HTML email directly, From = the authenticated mailbox."""
        import smtplib
        import ssl
        from email.mime.text import MIMEText
        from email.utils import formataddr
        msg = MIMEText(html_body or '', 'html', 'utf-8')
        msg['Subject'] = subject or 'ClickBuild'
        msg['From'] = formataddr(('ClickBuild', server.smtp_user))
        msg['To'] = to_addr
        ctx = ssl.create_default_context()
        if (server.smtp_encryption or 'ssl') == 'ssl':
            smtp = smtplib.SMTP_SSL(server.smtp_host, server.smtp_port or 465,
                                    timeout=20, context=ctx)
        else:
            smtp = smtplib.SMTP(server.smtp_host, server.smtp_port or 587, timeout=20)
            smtp.starttls(context=ctx)
        try:
            if server.smtp_user:
                smtp.login(server.smtp_user, server.smtp_pass or '')
            smtp.sendmail(server.smtp_user, [to_addr], msg.as_string())
        finally:
            smtp.quit()

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
                'industry': data.get('industry', ''),
                'expected_users': data.get('expected_users', ''),
                'requested_service': data.get('requested_service', ''),
                'message': data.get('message', ''), 'source': data.get('source', 'contact_form'),
                'country': data.get('country', ''), 'language': data.get('language', 'ar'),
                'newsletter_opt_in': data.get('newsletter', False)})
            return {'success': True, 'lead_id': lead.id}
        except Exception as e:
            _logger.error('Lead capture failed: %s', e)
            return {'success': False, 'error': str(e)}
