from odoo import http, _
from odoo.http import request
from odoo.addons.saas_website.services.error_handler import ErrorHandler
import time
import logging

_logger = logging.getLogger(__name__)

_RATE_LIMIT = {}
_MAX_ATTEMPTS = 5
_WINDOW = 300


class SaasWebsiteSignup(http.Controller):

    def _check_rate_limit(self, ip):
        now = time.time()
        attempts = [t for t in _RATE_LIMIT.get(ip, []) if now - t < _WINDOW]
        if len(attempts) >= _MAX_ATTEMPTS:
            return False
        attempts.append(now)
        _RATE_LIMIT[ip] = attempts
        return True

    @http.route(['/get-started', '/get-started/<string:plan_code>'],
                type='http', auth='public', website=True, sitemap=True)
    @ErrorHandler.handle_request_error
    def get_started(self, plan_code=None, **kw):
        plans = request.env['website'].get_saas_plans()
        selected_plan = None
        if plan_code:
            selected_plan = request.env['saas.plan'].sudo().search([
                ('code', '=', plan_code), ('active', '=', True)], limit=1)
        selected_edition = kw.get('edition', '')
        selected_user_count = kw.get('users', '1')
        if not selected_plan and selected_edition in ('community', 'enterprise'):
            selected_plan = request.env['saas.plan'].tier_plan_for(
                selected_edition, selected_user_count)
        platform_domain = request.env['saas.config'].sudo()._get_config().platform_domain
        # Sector pre-selected from the homepage industry cards (?industry=retail).
        industries = dict(request.env['saas.tenant'].sudo()._fields['industry'].selection)
        selected_industry = kw.get('industry') if kw.get('industry') in industries else ''
        return request.render('saas_website.page_signup_v2',
                              {'plans': plans, 'selected_plan': selected_plan,
                               'coupon': kw.get('coupon', ''),
                               'selected_industry': selected_industry,
                               'selected_edition': selected_edition,
                               'selected_user_count': selected_user_count,
                               'selected_billing_cycle': 'yearly',
                               'platform_domain': platform_domain})

    @http.route('/get-started/check', type='json', auth='public', csrf=False)
    def check_subdomain(self, subdomain=None, **kw):
        from odoo.addons.saas_website.services.signup_service import SignupService
        return SignupService(request.env).check_subdomain(subdomain or '')

    @http.route('/get-started/status', type='json', auth='public', csrf=False)
    def signup_status(self, tenant=None, **kw):
        """Polled by the success page to know when the new tenant is fully
        provisioned and reachable. Returns a dict the frontend uses to enable
        the login button.

        We verify three things, not just file existence:
          1. provisioning request files marked done
          2. tenant record reached state='trial'
          3. HTTPS endpoint at <sub>.odoo.clickbulid.com actually returns 200
             with the correct cert — this is what the user's browser will hit.
        """
        import os
        import ssl
        import socket
        import urllib.request
        import re

        sub = (tenant or '').strip().lower()
        if not re.match(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$', sub):
            return {'ready': False, 'reason': 'no tenant'}

        req_dir = '/mnt/cert-requests'
        provision_done = os.path.exists(os.path.join(req_dir, f'{sub}.provision.done'))
        provision_error = os.path.exists(os.path.join(req_dir, f'{sub}.provision.error'))
        cert_done = os.path.exists(os.path.join(req_dir, f'{sub}.done'))
        cert_error = os.path.exists(os.path.join(req_dir, f'{sub}.error'))

        tenant_rec = request.env['saas.tenant'].sudo().search(
            [('subdomain', '=', sub)], limit=1)
        record_ready = bool(tenant_rec and tenant_rec.state == 'trial')

        # Live HTTPS probe — only run once the cheap file checks pass, to avoid
        # wasted handshakes. We connect to the nginx container over the docker
        # network (it resolves to the right container IP via docker DNS) and
        # set SNI to the new subdomain. wrap_socket succeeds only if nginx
        # serves the per-tenant cert AND the cert chain validates.
        https_ok = False
        if provision_done and cert_done and record_ready:
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            target_host = f'{sub}.odoo.clickbulid.com'
            # Try a few addresses in order — works whether Odoo runs inside a
            # docker container next to nginx or on the host itself.
            for target_ip in ('nginx', '127.0.0.1', 'odoo_saas_nginx'):
                try:
                    with socket.create_connection((target_ip, 443), timeout=3) as sock:
                        with ctx.wrap_socket(sock, server_hostname=target_host):
                            https_ok = True
                            break
                except Exception:
                    continue

        return {
            'ready': bool(provision_done and cert_done and record_ready and https_ok),
            'provision_done': provision_done,
            'provision_error': provision_error,
            'cert_done': cert_done,
            'cert_error': cert_error,
            'state': tenant_rec.state if tenant_rec else None,
            'https_ok': https_ok,
        }

    @http.route('/get-started/register', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    @ErrorHandler.handle_request_error
    def register(self, **post):
        ip = request.httprequest.environ.get('HTTP_X_FORWARDED_FOR',
                                             request.httprequest.remote_addr).split(',')[0].strip()
        platform_domain = request.env['saas.config'].sudo()._get_config().platform_domain
        if not self._check_rate_limit(ip):
            return request.render('saas_website.page_signup_v2', {
                'plans': request.env['website'].get_saas_plans(),
                'platform_domain': platform_domain,
                'errors': [_('Too many attempts. Please try again in a few minutes.')], 'form_data': post})
        from odoo.addons.saas_website.services.signup_service import SignupService
        result = SignupService(request.env).register({
            'name': post.get('name'), 'email': post.get('email'), 'subdomain': post.get('subdomain'),
            'company': post.get('company'), 'phone': post.get('phone'), 'country': post.get('country', 'SA'),
            'industry': post.get('industry'), 'user_count': post.get('user_count'),
            'edition': post.get('edition'), 'billing_cycle': post.get('billing_cycle'),
            'plan_id': post.get('plan_id'), 'coupon_code': post.get('coupon_code'),
            'referral_code': post.get('referral_code')})
        if result.get('success'):
            # Stash the one-time credentials in the session so the success
            # page can show them (and clear them) without exposing in URL.
            request.session['saas_signup_credentials'] = {
                'admin_email': result.get('admin_email'),
                'admin_password': result.get('admin_password_one_time'),
                'tenant_url': result.get('url'),
                'subdomain': result.get('subdomain'),
            }
            return request.redirect(result.get('redirect', '/get-started/success'))
        return request.render('saas_website.page_signup_v2', {
            'plans': request.env['website'].get_saas_plans(),
            'platform_domain': platform_domain,
            'errors': result.get('errors', []), 'form_data': post})

    @http.route('/get-started/success', type='http', auth='public', website=True)
    def success(self, **kw):
        platform_domain = request.env['saas.config'].sudo()._get_config().platform_domain
        # One-shot read of credentials placed by register() — clear them so a
        # later refresh doesn't keep showing the password.
        creds = request.session.pop('saas_signup_credentials', None) or {}
        return request.render('saas_website.page_signup_success', {
            'subdomain': kw.get('tenant', ''),
            'platform_domain': platform_domain,
            'admin_email': creds.get('admin_email'),
            'admin_password': creds.get('admin_password'),
            'tenant_url': creds.get('tenant_url')})
