from odoo import http
from odoo.http import request


class SaasPortalKnowledge(http.Controller):

    @http.route('/my/saas/help', type='http', auth='user', website=True)
    def help_center(self, search=None, **kw):
        domain = [('state', '=', 'published'), ('visibility', 'in', ['public', 'portal'])]
        if search:
            domain += ['|', ('name', 'ilike', search), ('summary', 'ilike', search)]
        articles = request.env['saas.kb.article'].sudo().search(domain, limit=50)
        categories = request.env['saas.kb.category'].sudo().search([
            ('active', '=', True), ('parent_id', '=', False)])
        featured = request.env['saas.kb.article'].sudo().search(
            [('state', '=', 'published'), ('is_featured', '=', True)], limit=6)
        return request.render('saas_knowledge.portal_help_index', {
            'articles': articles, 'categories': categories,
            'featured': featured, 'search': search or '',
            'page_name': 'saas_help',
        })

    @http.route('/my/saas/help/category/<string:slug>', type='http',
                auth='user', website=True)
    def help_category(self, slug, **kw):
        category = request.env['saas.kb.category'].sudo().search(
            [('slug', '=', slug)], limit=1)
        if not category:
            return request.redirect('/my/saas/help')
        articles = request.env['saas.kb.article'].sudo().search([
            ('category_id', '=', category.id), ('state', '=', 'published'),
            ('visibility', 'in', ['public', 'portal'])])
        return request.render('saas_knowledge.portal_help_category', {
            'category': category, 'articles': articles, 'page_name': 'saas_help',
        })

    @http.route('/my/saas/help/article/<string:slug>', type='http',
                auth='user', website=True)
    def help_article(self, slug, **kw):
        article = request.env['saas.kb.article'].sudo().search(
            [('slug', '=', slug), ('state', '=', 'published')], limit=1)
        if not article:
            return request.redirect('/my/saas/help')
        article.increment_view_count()
        return request.render('saas_knowledge.portal_help_article', {
            'article': article, 'page_name': 'saas_help',
        })

    @http.route('/my/saas/help/article/<int:article_id>/feedback', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def article_feedback(self, article_id, **post):
        article = request.env['saas.kb.article'].sudo().browse(article_id)
        if article.exists():
            is_helpful = post.get('helpful') == '1'
            article.record_feedback(is_helpful, post.get('comment'))
        return request.redirect(f'/my/saas/help/article/{article.slug}')
