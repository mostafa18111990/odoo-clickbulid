from odoo import http
from odoo.http import request


class SaasWebsiteMain(http.Controller):

    @http.route('/switch-lang/<string:lang_code>', type='http', auth='public', website=True, sitemap=False)
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
    def homepage(self, **kw):
        plans = request.env['website'].get_saas_plans()
        faqs = request.env['website'].get_featured_faqs(limit=6)
        return request.render('saas_website.page_home', {'plans': plans, 'faqs': faqs})

    @http.route('/features', type='http', auth='public', website=True, sitemap=True)
    def features(self, **kw):
        return request.render('saas_website.page_features', {})

    @http.route('/pricing', type='http', auth='public', website=True, sitemap=True)
    def pricing(self, **kw):
        return request.render('saas_website.page_pricing', {'plans': request.env['website'].get_saas_plans()})

    @http.route('/faq', type='http', auth='public', website=True, sitemap=True)
    def faq(self, **kw):
        return request.render('saas_website.page_faq', {'faqs': request.env['website'].get_featured_faqs(limit=50)})

    @http.route('/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kw):
        return request.render('saas_website.page_contact', {'submitted': kw.get('submitted')})

    @http.route('/contact/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def contact_submit(self, **post):
        from odoo.addons.saas_website.services.signup_service import SignupService
        SignupService(request.env).capture_lead({
            'name': post.get('name'), 'email': post.get('email'), 'phone': post.get('phone'),
            'company': post.get('company'), 'message': post.get('message'), 'source': 'contact_form'})
        return request.redirect('/contact?submitted=1')

    @http.route('/newsletter/subscribe', type='json', auth='public', csrf=False)
    def newsletter_subscribe(self, email=None, **kw):
        if not email:
            return {'success': False}
        from odoo.addons.saas_website.services.signup_service import SignupService
        return SignupService(request.env).capture_lead({
            'name': email.split('@')[0], 'email': email, 'source': 'newsletter', 'newsletter': True})
