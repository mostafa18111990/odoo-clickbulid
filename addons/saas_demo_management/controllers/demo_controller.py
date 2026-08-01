import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

from odoo.addons.saas_demo_management.models.demo_template import SECTOR_SELECTION


SECTOR_LABELS_AR = {
    'construction': 'المقاولات',
    'trading-distribution': 'التجارة والتوزيع',
    'retail': 'التجزئة',
    'restaurants-cafes': 'المطاعم والمقاهي',
    'manufacturing': 'التصنيع',
    'professional-services': 'الخدمات المهنية',
    'real-estate': 'العقارات وإدارة الأملاك',
    'ecommerce': 'التجارة الإلكترونية',
    'field-services': 'الصيانة والخدمات الميدانية',
    'education': 'التعليم والتدريب',
    'startups-smes': 'الشركات الناشئة والمنشآت الصغيرة والمتوسطة',
}


class SaasDemoWebsite(http.Controller):
    SESSION_KEY = 'saas_demo_public_status'

    def _bind_demo_to_session(self, demo):
        raw_token = secrets.token_urlsafe(32)
        demo.sudo().write({
            'public_status_token_hash': hashlib.sha256(
                raw_token.encode('utf-8')).hexdigest(),
        })
        request.session[self.SESSION_KEY] = {
            'demo_id': demo.id,
            'token': raw_token,
        }

    def _session_demo(self):
        session_data = request.session.get(self.SESSION_KEY) or {}
        demo_id = session_data.get('demo_id')
        raw_token = session_data.get('token') or ''
        if not isinstance(demo_id, int) or not raw_token:
            return request.env['saas.demo.request']
        demo = request.env['saas.demo.request'].sudo().browse(demo_id).exists()
        supplied_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        if not demo or not demo.public_status_token_hash or not hmac.compare_digest(
                supplied_hash, demo.public_status_token_hash):
            return request.env['saas.demo.request']
        return demo

    @http.route('/demo/request', type='http', auth='public', website=True, sitemap=True)
    def demo_request(self, **kw):
        sectors = dict(SECTOR_SELECTION)
        selected = kw.get('industry') if kw.get('industry') in sectors else ''
        is_arabic = request.env.lang in ('ar_001', 'ar')
        sector_options = [
            (code, SECTOR_LABELS_AR.get(code, label) if is_arabic else label)
            for code, label in SECTOR_SELECTION
        ]
        return request.render('saas_demo_management.page_demo_request', {
            'sectors': sector_options, 'selected_sector': selected,
            'form_error': kw.get('error')})

    @http.route('/demo/request/submit', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def demo_request_submit(self, **post):
        if post.get('website_url'):
            return request.redirect('/demo/request/success')
        sectors = dict(SECTOR_SELECTION)
        required = ('contact_name', 'company_name', 'email', 'phone', 'sector')
        if any(not (post.get(field) or '').strip() for field in required):
            return request.redirect('/demo/request?error=required')
        if post.get('sector') not in sectors:
            return request.redirect('/demo/request?error=sector')
        email = (post.get('email') or '').strip().lower()
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return request.redirect('/demo/request?error=email')
        if not post.get('privacy_consent'):
            return request.redirect('/demo/request?error=consent')

        remote = request.httprequest.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        remote = remote or request.httprequest.remote_addr or 'unknown'
        secret = request.env['ir.config_parameter'].sudo().get_param(
            'database.secret') or request.env.cr.dbname
        fingerprint = hashlib.sha256(('%s:%s' % (secret, remote)).encode()).hexdigest()
        Demo = request.env['saas.demo.request'].sudo()
        cutoff = fields.Datetime.now() - timedelta(minutes=15)
        raw_limit = request.env['ir.config_parameter'].sudo().get_param(
            'saas_demo.max_requests_per_15_minutes', '3')
        try:
            limit_value = max(1, min(int(raw_limit), 20))
        except ValueError:
            limit_value = 3
        if Demo.search_count([('source_fingerprint', '=', fingerprint),
                              ('create_date', '>=', cutoff)]) >= limit_value:
            return request.redirect('/demo/request?error=rate')
        duplicate = Demo.search([
            ('email', '=', email), ('sector', '=', post.get('sector')),
            ('create_date', '>=', fields.Datetime.now() - timedelta(hours=24)),
            ('state', 'not in', ('rejected', 'deleted'))], limit=1)
        if duplicate:
            return request.redirect('/demo/request/success')

        def safe_int(value, default, minimum, maximum):
            try:
                return max(minimum, min(int(value), maximum))
            except (TypeError, ValueError):
                return default

        template = request.env['saas.demo.template'].sudo().search([
            ('sector', '=', post.get('sector')), ('active', '=', True)], limit=1)
        demo = Demo.create({
            'contact_name': post.get('contact_name').strip(),
            'company_name': post.get('company_name').strip(),
            'email': email, 'phone': post.get('phone').strip(),
            'city': (post.get('city') or '').strip(),
            'country_code': (post.get('country_code') or 'SA')[:2].upper(),
            'sector': post.get('sector'), 'template_id': template.id if template else False,
            'user_count': safe_int(post.get('user_count'), 5, 1, 100),
            'company_size': post.get('company_size') if post.get('company_size') in (
                'micro', 'small', 'medium', 'large') else False,
            'branch_count': safe_int(post.get('branch_count'), 1, 1, 1000),
            'requested_apps': (post.get('requested_apps') or '')[:2000],
            'preferred_contact_channel': post.get('preferred_contact_channel')
                if post.get('preferred_contact_channel') in ('phone', 'whatsapp', 'email', 'meeting')
                else 'phone',
            'preferred_contact_time': (post.get('preferred_contact_time') or '')[:240],
            'notes': (post.get('notes') or '')[:4000], 'privacy_consent': True,
            'utm_source': (post.get('utm_source') or '')[:240],
            'utm_medium': (post.get('utm_medium') or '')[:240],
            'utm_campaign': (post.get('utm_campaign') or '')[:240],
            'utm_term': (post.get('utm_term') or '')[:240],
            'utm_content': (post.get('utm_content') or '')[:240],
            'landing_url': (post.get('landing_url') or request.httprequest.referrer or '')[:500],
            'referrer_url': (post.get('referrer_url') or request.httprequest.referrer or '')[:500],
            'consent_at': fields.Datetime.now(),
            'source_fingerprint': fingerprint,
            'duration_days': template.default_duration_days if template else 14})
        demo.action_submit_for_review()
        self._bind_demo_to_session(demo)
        return request.redirect('/demo/request/success')

    @http.route('/demo/request/success', type='http', auth='public', website=True,
                sitemap=False)
    def demo_request_success(self, **kw):
        demo = self._session_demo()
        response = request.render('saas_demo_management.page_demo_request_success', {
            'has_demo_status': bool(demo),
        })
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @http.route('/demo/request/status.json', type='http', auth='public',
                methods=['GET'], csrf=False, sitemap=False)
    def demo_request_status(self, **kw):
        demo = self._session_demo()
        if not demo:
            response = request.make_json_response(
                {'ok': False, 'error': 'not_found'}, status=404)
            response.headers['Cache-Control'] = 'no-store, private'
            return response

        state_messages = {
            'new': ('received', 10),
            'pending_review': ('pending_review', 20),
            'needs_info': ('needs_info', 20),
            'approved': ('approved', 35),
            'queued': ('queued', 45),
            'provisioning': ('provisioning', 65),
            'ready': ('checking', 85),
            'active': ('ready', 100),
            'extended': ('ready', 100),
            'rejected': ('rejected', 100),
            'failed': ('failed', 100),
            'expired': ('expired', 100),
            'suspended': ('expired', 100),
            'deleted': ('expired', 100),
            'converted': ('converted', 100),
        }
        status_code, progress = state_messages.get(demo.state, ('processing', 30))
        tenant = demo.tenant_id
        if (
            demo.state in ('ready', 'active', 'extended')
            and demo.health_status != 'healthy'
        ):
            demo._refresh_public_readiness_if_due()
            tenant = demo.tenant_id
        is_ready = bool(
            tenant
            and demo.state in ('ready', 'active', 'extended')
            and demo.health_status == 'healthy'
            and tenant.demo_sandbox_state == 'enforced'
            and tenant.api_instance_id
            and not tenant.api_instance_id.startswith('pending:')
            and tenant.admin_login
            and tenant.admin_password
        )
        payload = {
            'ok': True,
            'request_name': demo.name,
            'state': demo.state,
            'status_code': 'ready' if is_ready else status_code,
            'progress': 100 if is_ready else progress,
            'terminal': demo.state in (
                'rejected', 'failed', 'expired', 'suspended',
                'deleted', 'converted'),
            'ready': is_ready,
        }
        if is_ready:
            payload['credentials'] = {
                'url': 'https://%s.odoo.clickbulid.com/web/login' % tenant.subdomain,
                'username': tenant.admin_login,
                'password': tenant.admin_password,
                'expires_at': fields.Datetime.to_string(
                    demo.expires_at or tenant.demo_expires_at),
            }
            if not demo.credentials_revealed_at:
                demo.sudo().write({'credentials_revealed_at': fields.Datetime.now()})
        response = request.make_json_response(payload)
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
