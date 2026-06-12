from odoo import http
from odoo.http import request


class SaasWebsiteKnowledge(http.Controller):

    @http.route('/help', type='http', auth='public', website=True)
    def public_help(self, search=None, **kw):
        domain = [('state', '=', 'published'), ('visibility', '=', 'public')]
        if search:
            domain += ['|', ('name', 'ilike', search), ('summary', 'ilike', search)]
        articles = request.env['saas.kb.article'].sudo().search(domain, limit=50)
        categories = request.env['saas.kb.category'].sudo().search([
            ('active', '=', True), ('parent_id', '=', False)])
        featured = request.env['saas.kb.article'].sudo().search(
            [('state', '=', 'published'), ('visibility', '=', 'public'),
             ('is_featured', '=', True)], limit=6)
        return request.render('saas_knowledge.website_help_index', {
            'articles': articles, 'categories': categories,
            'featured': featured, 'search': search or '',
        })

    @http.route('/help/<string:slug>', type='http', auth='public', website=True)
    def public_article(self, slug, **kw):
        article = request.env['saas.kb.article'].sudo().search(
            [('slug', '=', slug), ('state', '=', 'published'),
             ('visibility', '=', 'public')], limit=1)
        if not article:
            return request.redirect('/help')
        article.increment_view_count()
        return request.render('saas_knowledge.website_help_article', {'article': article})
