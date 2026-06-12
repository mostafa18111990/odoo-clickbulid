from odoo import models, fields, api


class SaasKbArticle(models.Model):
    _name = 'saas.kb.article'
    _description = 'Knowledge Base Article'
    _order = 'sequence, name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Title', required=True, translate=True, tracking=True)
    slug = fields.Char(string='Slug', required=True, index=True)
    category_id = fields.Many2one('saas.kb.category', string='Category',
                                  required=True, ondelete='restrict', tracking=True)
    summary = fields.Text(string='Summary', translate=True)
    body = fields.Html(string='Body', sanitize=True, translate=True)
    tags = fields.Char(string='Tags')
    author_id = fields.Many2one('res.users', string='Author',
                                default=lambda self: self.env.uid, tracking=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('review', 'In Review'),
                   ('published', 'Published'), ('archived', 'Archived')],
        string='State', default='draft', required=True, tracking=True, index=True)
    sequence = fields.Integer(default=10)
    visibility = fields.Selection(
        selection=[('public', 'Public'), ('portal', 'Portal Only'), ('internal', 'Internal')],
        string='Visibility', default='public', required=True, index=True)
    is_featured = fields.Boolean(string='Featured', default=False, index=True)
    view_count = fields.Integer(string='Views', default=0, readonly=True)
    helpful_count = fields.Integer(string='Helpful Votes', default=0, readonly=True)
    not_helpful_count = fields.Integer(string='Not Helpful Votes', default=0, readonly=True)
    feedback_ids = fields.One2many('saas.kb.feedback', 'article_id', string='Feedback')
    published_at = fields.Datetime(string='Published At', readonly=True)
    related_ticket_count = fields.Integer(string='Related Tickets', compute='_compute_related_tickets')
    active = fields.Boolean(default=True)

    _sql_constraints = [('slug_unique', 'UNIQUE(slug)', 'Slug must be unique.')]

    def _compute_related_tickets(self):
        for rec in self:
            rec.related_ticket_count = 0

    def action_publish(self):
        for rec in self:
            rec.write({'state': 'published',
                       'published_at': fields.Datetime.now()})

    def action_unpublish(self):
        self.write({'state': 'draft'})

    def action_archive_article(self):
        self.write({'state': 'archived', 'active': False})

    def increment_view_count(self):
        for rec in self:
            rec.sudo().view_count += 1

    def record_feedback(self, is_helpful, comment=None):
        self.ensure_one()
        self.env['saas.kb.feedback'].sudo().create({
            'article_id': self.id, 'is_helpful': bool(is_helpful),
            'comment': comment or '',
            'user_id': self.env.user.id if self.env.user.id else False,
        })
        if is_helpful:
            self.sudo().helpful_count += 1
        else:
            self.sudo().not_helpful_count += 1
