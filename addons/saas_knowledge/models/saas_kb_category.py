from odoo import models, fields, api


class SaasKbCategory(models.Model):
    _name = 'saas.kb.category'
    _description = 'Knowledge Base Category'
    _order = 'sequence, name'
    _parent_store = True
    _parent_name = 'parent_id'

    name = fields.Char(string='Name', required=True, translate=True)
    name_ar = fields.Char(string='Arabic Name')
    slug = fields.Char(string='Slug', required=True, index=True)
    description = fields.Text(string='Description')
    icon = fields.Char(string='Icon', default='fa-book')
    color = fields.Char(string='Color', default='#3b82f6')
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one('saas.kb.category', string='Parent', ondelete='cascade', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('saas.kb.category', 'parent_id', string='Subcategories')
    article_ids = fields.One2many('saas.kb.article', 'category_id', string='Articles')
    article_count = fields.Integer(string='Articles', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    _sql_constraints = [('slug_unique', 'UNIQUE(slug)', 'Slug must be unique.')]

    def _compute_article_count(self):
        for rec in self:
            rec.article_count = self.env['saas.kb.article'].search_count([
                ('category_id', '=', rec.id), ('state', '=', 'published')])
