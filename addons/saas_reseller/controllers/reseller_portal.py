from odoo import http
from odoo.http import request


class SaasResellerPortal(http.Controller):

    def _get_reseller(self):
        return request.env['saas.reseller'].sudo().search([
            ('portal_user_id', '=', request.env.user.id)], limit=1)

    @http.route('/reseller', type='http', auth='user', website=True)
    def reseller_dashboard(self, **kw):
        reseller = self._get_reseller()
        if not reseller:
            return request.redirect('/my')
        return request.render('saas_reseller.reseller_dashboard', {'reseller': reseller})

    @http.route('/reseller/customers', type='http', auth='user', website=True)
    def reseller_customers(self, **kw):
        reseller = self._get_reseller()
        if not reseller:
            return request.redirect('/my')
        return request.render('saas_reseller.reseller_customers',
                              {'reseller': reseller, 'customers': reseller.tenant_ids})

    @http.route('/reseller/commissions', type='http', auth='user', website=True)
    def reseller_commissions(self, **kw):
        reseller = self._get_reseller()
        if not reseller:
            return request.redirect('/my')
        return request.render('saas_reseller.reseller_commissions',
                              {'reseller': reseller, 'commissions': reseller.commission_ids})

    @http.route('/reseller/payouts', type='http', auth='user', website=True)
    def reseller_payouts(self, **kw):
        reseller = self._get_reseller()
        if not reseller:
            return request.redirect('/my')
        return request.render('saas_reseller.reseller_payouts',
                              {'reseller': reseller, 'payouts': reseller.payout_ids})
