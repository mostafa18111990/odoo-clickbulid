from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.portal_main import SaasPortalMain
import logging

_logger = logging.getLogger(__name__)


class SaasPortalSupport(SaasPortalMain):

    @http.route('/my/saas/tickets', type='http', auth='user', website=True)
    def my_tickets(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        tickets = request.env['saas.ticket'].sudo().search([
            ('tenant_id', '=', tenant.id)], order='create_date desc')
        return request.render('saas_support.portal_my_tickets',
                              {'tenant': tenant, 'tickets': tickets, 'page_name': 'saas_tickets'})

    @http.route('/my/saas/tickets/new', type='http', auth='user', website=True)
    def new_ticket(self, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        categories = request.env['saas.ticket.category'].sudo().search([('active', '=', True)])
        priorities = request.env['saas.ticket.priority'].sudo().search([('active', '=', True)])
        return request.render('saas_support.portal_new_ticket',
                              {'tenant': tenant, 'categories': categories,
                               'priorities': priorities, 'page_name': 'saas_tickets'})

    @http.route('/my/saas/tickets/new/submit', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def submit_ticket(self, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        from odoo.addons.saas_support.services.ticket_service import TicketService
        try:
            ticket = TicketService(request.env(su=True)).create_ticket(
                subject=post.get('subject', '').strip(),
                description=post.get('description', '').strip(),
                tenant=tenant, portal_user=request.env.user,
                category_code=post.get('category_code'),
                priority_code=post.get('priority_code', 'normal'),
                customer_email=request.env.user.email, customer_name=request.env.user.name)
            return request.redirect(f'/my/saas/tickets/{ticket.id}')
        except Exception as e:
            return request.render('saas_support.portal_new_ticket', {
                'tenant': tenant,
                'categories': request.env['saas.ticket.category'].sudo().search([]),
                'priorities': request.env['saas.ticket.priority'].sudo().search([]),
                'error': str(e), 'page_name': 'saas_tickets'})

    @http.route('/my/saas/tickets/<int:ticket_id>', type='http', auth='user', website=True)
    def ticket_detail(self, ticket_id, **kw):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        ticket = request.env['saas.ticket'].sudo().search([
            ('id', '=', ticket_id), ('tenant_id', '=', tenant.id)], limit=1)
        if not ticket:
            return request.redirect('/my/saas/tickets')
        messages = ticket.message_ids_typed.filtered(lambda m: not m.is_internal)
        return request.render('saas_support.portal_ticket_detail',
                              {'tenant': tenant, 'ticket': ticket, 'messages': messages,
                               'page_name': 'saas_tickets'})

    @http.route('/my/saas/tickets/<int:ticket_id>/reply', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def reply_ticket(self, ticket_id, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        ticket = request.env['saas.ticket'].sudo().search([
            ('id', '=', ticket_id), ('tenant_id', '=', tenant.id)], limit=1)
        if not ticket:
            return request.redirect('/my/saas/tickets')
        body = post.get('body', '').strip()
        if body:
            from odoo.addons.saas_support.services.ticket_service import TicketService
            TicketService(request.env(su=True)).add_reply(
                ticket=ticket, body=body, author=request.env.user,
                is_internal=False, is_from_customer=True)
        return request.redirect(f'/my/saas/tickets/{ticket_id}')

    @http.route('/my/saas/tickets/<int:ticket_id>/close', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def close_ticket(self, ticket_id, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        ticket = request.env['saas.ticket'].sudo().search([
            ('id', '=', ticket_id), ('tenant_id', '=', tenant.id)], limit=1)
        if ticket and ticket.state == 'resolved':
            ticket.action_close()
        return request.redirect(f'/my/saas/tickets/{ticket_id}')

    @http.route('/my/saas/tickets/<int:ticket_id>/rate', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def rate_ticket(self, ticket_id, **post):
        tenant = self._get_my_tenant()
        if not tenant:
            return request.redirect('/my/saas')
        ticket = request.env['saas.ticket'].sudo().search([
            ('id', '=', ticket_id), ('tenant_id', '=', tenant.id)], limit=1)
        if ticket:
            rating = post.get('rating')
            comment = post.get('comment', '')
            if rating in ('1', '2', '3', '4', '5'):
                ticket.submit_csat(rating, comment)
        return request.redirect(f'/my/saas/tickets/{ticket_id}')
