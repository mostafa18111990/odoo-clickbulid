from odoo import http
from odoo.http import request


class SaasPortalMarketing(http.Controller):

    @http.route('/my/saas/referrals', type='http', auth='user', website=True)
    def my_referrals(self, **kw):
        referrals = request.env['saas.referral'].sudo().search([
            ('referrer_user_id', '=', request.env.user.id)], order='create_date desc')
        program = request.env['saas.referral.program'].sudo().search(
            [('active', '=', True)], limit=1)
        return request.render('saas_marketing.portal_my_referrals', {
            'referrals': referrals, 'program': program,
            'page_name': 'saas_referrals'})

    @http.route('/my/saas/referrals/new', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def create_referral(self, **post):
        from odoo.addons.saas_marketing.services.referral_service import ReferralService
        ReferralService(request.env(su=True)).create_referral(
            request.env.user, email=post.get('email'))
        return request.redirect('/my/saas/referrals')
