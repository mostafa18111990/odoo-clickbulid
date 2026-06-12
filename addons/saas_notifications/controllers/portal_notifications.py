from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain


class SaasPortalNotifications(SaasPortalMain):

    @http.route('/my/saas/notifications', type='http', auth='user', website=True)
    def saas_notifications(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        notifications = request.env['saas.notification'].sudo().search([
            ('user_id', '=', request.env.user.id), ('channel', '=', 'inapp')],
            order='create_date desc', limit=50)
        return request.render('saas_notifications.portal_notifications',
                              {'tenant': tenant, 'notifications': notifications, 'page_name': 'saas_notifications'})

    @http.route('/my/saas/notifications/<int:notif_id>/read', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def mark_read(self, notif_id, **kw):
        notif = request.env['saas.notification'].sudo().search([
            ('id', '=', notif_id), ('user_id', '=', request.env.user.id)], limit=1)
        if notif:
            notif.mark_read()
        return request.redirect('/my/saas/notifications')

    @http.route('/my/saas/preferences', type='http', auth='user', website=True)
    def saas_preferences(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        pref = request.env['saas.notification.preference'].sudo().get_or_create(tenant)
        return request.render('saas_notifications.portal_preferences',
                              {'tenant': tenant, 'pref': pref, 'saved': kw.get('saved'), 'page_name': 'saas_preferences'})

    @http.route('/my/saas/preferences/save', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def save_preferences(self, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        pref = request.env['saas.notification.preference'].sudo().get_or_create(tenant)
        fields_map = ['billing_email', 'billing_sms', 'subscription_email', 'subscription_sms',
                      'lifecycle_email', 'lifecycle_sms', 'technical_email', 'technical_inapp',
                      'marketing_email', 'marketing_sms', 'digest_mode']
        pref.sudo().write({f: (f in post) for f in fields_map})
        return request.redirect('/my/saas/preferences?saved=1')
