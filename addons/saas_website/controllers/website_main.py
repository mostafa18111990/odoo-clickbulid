from odoo import http
from odoo.http import request
from odoo.addons.account.controllers.terms import TermsController
from odoo.addons.saas_website.services.error_handler import ErrorHandler, HealthCheck, PlatformError
from .content_catalog import APPLICATIONS, INDUSTRIES, SERVICES


def _published_content(model_name):
    """Return published records for this website when ClickBuild 3 is installed."""
    if model_name not in request.env.registry:
        return []
    website = request.website or request.env['website'].get_current_website()
    return request.env[model_name].sudo().search([
        ('website_id', '=', website.id),
        ('active', '=', True),
        ('published', '=', True),
    ], order='sequence, id')


def _application_catalog():
    if 'clickbuild.application' not in request.env.registry:
        return list(APPLICATIONS.values())
    return [record._catalog_dict() for record in _published_content('clickbuild.application')]


def _industry_catalog():
    if 'clickbuild.industry' not in request.env.registry:
        return list(INDUSTRIES.values())
    return [record._catalog_dict() for record in _published_content('clickbuild.industry')]


def _service_catalog():
    if 'clickbuild.service' not in request.env.registry:
        return SERVICES
    return [(record.name, record.summary) for record in _published_content('clickbuild.service')]


class SaasWebsiteMain(http.Controller):

    @http.route('/switch-lang/<string:lang_code>', type='http', auth='public', website=True, sitemap=False)
    @ErrorHandler.handle_request_error
    def switch_lang(self, lang_code, **kw):
        """Force-switch the website language and redirect to the requested path.
        Bypasses Odoo's session-lang persistence that would otherwise re-redirect
        /pricing back to /en/pricing for a user whose session lang is still en_US.
        """
        from werkzeug.urls import url_unquote
        Lang = request.env['res.lang'].sudo()
        lang = Lang.search([('code', '=', lang_code), ('active', '=', True)], limit=1)
        if not lang:
            return request.redirect('/')
        # Update session lang so subsequent navigation honours the new choice.
        request.session['lang'] = lang.code
        target = url_unquote(kw.get('r') or '/')
        if not target.startswith('/'):
            target = '/'
        # Strip any existing lang prefix from the target.
        for prefix in ('/en/', '/ar/'):
            if target.startswith(prefix):
                target = '/' + target[len(prefix):]
                break
            if target == prefix.rstrip('/'):
                target = '/'
                break
        default_code = (request.website.default_lang_id.code
                        if getattr(request, 'website', None) and request.website.default_lang_id
                        else 'ar_001')
        # Re-add a URL prefix only for non-default languages.
        if lang.code != default_code and lang.url_code:
            target = '/' + lang.url_code + ('' if target == '/' else target)
        resp = request.redirect(target)
        # Persist the choice across browser sessions.
        resp.set_cookie('frontend_lang', lang.code, max_age=365 * 24 * 60 * 60)
        return resp

    @http.route('/', type='http', auth='public', website=True, sitemap=True)
    @ErrorHandler.handle_request_error
    def homepage(self, **kw):
        plans = request.env['website'].get_saas_plans()
        faqs = request.env['website'].get_featured_faqs(limit=6)
        return request.render('saas_website.page_home', {'plans': plans, 'faqs': faqs})

    @http.route('/features', type='http', auth='public', website=True, sitemap=True)
    def features(self, **kw):
        return request.render('saas_website.page_features', {'applications': _application_catalog()})

    @http.route('/apps', type='http', auth='public', website=True, sitemap=True)
    def apps(self, **kw):
        return request.render('saas_website.page_catalog', {
            'catalog_kind': 'apps', 'items': _application_catalog()})

    @http.route('/apps/<string:slug>', type='http', auth='public', website=True, sitemap=True)
    def app_detail(self, slug, **kw):
        if 'clickbuild.application' in request.env.registry:
            record = _published_content('clickbuild.application').filtered(lambda row: row.slug == slug)[:1]
            item = record._catalog_dict() if record else None
        else:
            item = APPLICATIONS.get(slug)
        if not item:
            return request.not_found()
        return request.render('saas_website.page_solution_detail', {'item': item})

    @http.route('/industries', type='http', auth='public', website=True, sitemap=True)
    def industries(self, **kw):
        return request.render('saas_website.page_catalog', {
            'catalog_kind': 'industries', 'items': _industry_catalog()})

    @http.route('/industries/<string:slug>', type='http', auth='public', website=True, sitemap=True)
    def industry_detail(self, slug, **kw):
        if 'clickbuild.industry' in request.env.registry:
            record = _published_content('clickbuild.industry').filtered(lambda row: row.slug == slug)[:1]
            item = record._catalog_dict() if record else None
        else:
            item = INDUSTRIES.get(slug)
        if not item:
            return request.not_found()
        return request.render('saas_website.page_solution_detail', {'item': item})

    @http.route('/services', type='http', auth='public', website=True, sitemap=True)
    def services(self, **kw):
        return request.render('saas_website.page_services', {'services': _service_catalog()})

    @http.route('/pricing', type='http', auth='public', website=True, sitemap=True)
    def pricing(self, **kw):
        return request.render('saas_website.page_pricing_v3', {'plans': request.env['website'].get_saas_plans()})

    @http.route('/faq', type='http', auth='public', website=True, sitemap=True)
    def faq(self, **kw):
        return request.render('saas_website.page_faq', {'faqs': request.env['website'].get_featured_faqs(limit=50)})

    @http.route('/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kw):
        return request.render('saas_website.page_contact', {
            'submitted': kw.get('submitted'), 'form_error': kw.get('error')})

    @http.route('/contact/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def contact_submit(self, **post):
        from odoo.addons.saas_website.services.signup_service import SignupService
        if not (post.get('name') and post.get('email') and post.get('message')):
            return request.redirect('/contact?error=required')
        result = SignupService(request.env).capture_lead({
            'name': post.get('name'), 'email': post.get('email'), 'phone': post.get('phone'),
            'company': post.get('company'), 'industry': post.get('industry'),
            'expected_users': post.get('expected_users'),
            'requested_service': post.get('requested_service') or post.get('inquiry_type'),
            'message': post.get('message'), 'source': 'contact_form'})
        return request.redirect('/contact?submitted=1' if result.get('success') else '/contact?error=save')

    @http.route('/newsletter/subscribe', type='jsonrpc', auth='public', csrf=False)
    def newsletter_subscribe(self, email=None, **kw):
        if not email:
            return {'success': False}
        from odoo.addons.saas_website.services.signup_service import SignupService
        return SignupService(request.env).capture_lead({
            'name': email.split('@')[0], 'email': email, 'source': 'newsletter', 'newsletter': True})

    @http.route('/about', type='http', auth='public', website=True, sitemap=True)
    def about(self, **kw):
        return request.render('saas_website.page_about', {})

    @http.route('/privacy', type='http', auth='public', website=True, sitemap=True)
    def privacy(self, **kw):
        return request.render('saas_website.page_legal', {'page': 'privacy'})

    @http.route('/dpa', type='http', auth='public', website=True, sitemap=True)
    def dpa(self, **kw):
        return request.render('saas_website.page_legal', {'page': 'dpa'})

    @http.route('/sla', type='http', auth='public', website=True, sitemap=True)
    def sla(self, **kw):
        return request.render('saas_website.page_legal', {'page': 'sla'})

    @http.route('/health', type='jsonrpc', auth='public', csrf=False)
    def health_check(self, **kw):
        """Platform health status endpoint."""
        return HealthCheck.get_platform_status()

    @http.route('/error', type='http', auth='public', website=True)
    def error_page(self, code='UNKNOWN', **kw):
        """Graceful error page."""
        lang = request.env.lang if hasattr(request, 'env') else 'ar'
        error_msg = ErrorHandler.get_graceful_response(code, lang)
        return request.render('saas_website.page_error', {
            'error_code': code,
            'error_message': error_msg
        })


class SaasWebsiteTerms(TermsController):
    """Override Odoo Accounting's /terms controller with the platform terms."""

    @http.route()
    def terms_conditions(self, **kwargs):
        return request.render('saas_website.page_legal', {'page': 'terms'})
