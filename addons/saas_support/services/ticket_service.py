from odoo import _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, env):
        self.env = env

    def create_ticket(self, subject, description, tenant=None, portal_user=None,
                      category_code=None, priority_code='normal',
                      customer_email=None, customer_name=None):
        if not subject:
            raise UserError(_('Subject is required.'))
        category = None
        if category_code:
            category = self.env['saas.ticket.category'].sudo().search([
                ('code', '=', category_code)], limit=1)
        priority = self.env['saas.ticket.priority'].sudo().search([('code', '=', priority_code)], limit=1)
        if not priority:
            priority = self.env['saas.ticket.priority'].sudo().search([], limit=1)
        if not priority:
            raise UserError(_('No ticket priority configured.'))
        team = 'platform'
        if tenant and tenant.reseller_id:
            team = 'reseller'
        ticket = self.env['saas.ticket'].sudo().create({
            'subject': subject, 'description': description,
            'tenant_id': tenant.id if tenant else False,
            'portal_user_id': portal_user.id if portal_user else False,
            'customer_name': customer_name or (tenant.customer_name if tenant else ''),
            'customer_email': customer_email or (tenant.customer_email if tenant else ''),
            'category_id': category.id if category else False,
            'priority_id': priority.id, 'team': team, 'state': 'new'})
        _logger.info('Ticket created: %s for %s', ticket.name, ticket.customer_email)
        return ticket

    def add_reply(self, ticket, body, author=None, is_internal=False,
                  is_from_customer=False, attachment_ids=None):
        author = author or self.env.user
        message = self.env['saas.ticket.message'].sudo().create({
            'ticket_id': ticket.id, 'author_id': author.id, 'author_name': author.name,
            'author_email': author.email, 'body': body, 'is_internal': is_internal,
            'is_from_customer': is_from_customer,
            'attachment_ids': [(6, 0, attachment_ids or [])]})
        if is_from_customer:
            if ticket.state == 'waiting_customer':
                ticket.sudo().write({'state': 'in_progress'})
        else:
            if ticket.state == 'new':
                ticket.sudo().write({'state': 'in_progress', 'assignee_id': author.id})
        return message
