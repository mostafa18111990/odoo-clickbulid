import hashlib
import re
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

from odoo.addons.saas_demo_management.models.demo_template import SECTOR_SELECTION


class SaasDemoWebsite(http.Controller):

    @http.route('/demo/request', type='http', auth='public', website=True, sitemap=True)
    def demo_request(self, **kw):
        sectors = dict(SECTOR_SELECTION)
        selected = kw.get('industry') if kw.get('industry') in sectors else ''
        return request.render('saas_demo_management.page_demo_request', {
            'sectors': SECTOR_SELECTION, 'selected_sector': selected,
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
            'landing_url': (post.get('landing_url') or request.httprequest.referrer or '')[:500],
            'source_fingerprint': fingerprint,
            'duration_days': template.default_duration_days if template else 14})
        demo.action_submit_for_review()
        return request.redirect('/demo/request/success')

    @http.route('/demo/request/success', type='http', auth='public', website=True,
                sitemap=False)
    def demo_request_success(self, **kw):
        return request.render('saas_demo_management.page_demo_request_success', {})
