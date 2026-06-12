from odoo import models, fields, api


class SaasTicketMessage(models.Model):
    _name = 'saas.ticket.message'
    _description = 'Ticket Message'
    _order = 'create_date'
    _rec_name = 'subject'

    ticket_id = fields.Many2one('saas.ticket', string='Ticket', required=True,
                                ondelete='cascade', index=True)
    author_id = fields.Many2one('res.users', string='Author', default=lambda self: self.env.uid, index=True)
    author_name = fields.Char(string='Author Name')
    author_email = fields.Char(string='Author Email')
    subject = fields.Char(string='Subject')
    body = fields.Html(string='Body', sanitize=True)
    is_internal = fields.Boolean(string='Internal Note', default=False)
    is_from_customer = fields.Boolean(string='From Customer', default=False)
    attachment_ids = fields.Many2many('ir.attachment',
        'saas_ticket_message_attachment_rel', 'message_id', 'attachment_id',
        string='Attachments')

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for msg in messages:
            if not msg.is_internal and not msg.is_from_customer and msg.ticket_id:
                msg.ticket_id.record_first_response()
        return messages
