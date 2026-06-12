from odoo import models, fields, api


class SaasMarketplaceCategory(models.Model):
    _name = 'saas.marketplace.category'
    _description = 'Marketplace Category'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    name_ar = fields.Char(string='الاسم')
    code = fields.Char(string='Code', required=True, index=True)
    icon = fields.Char(string='Icon', default='fa-cube')
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    app_ids = fields.One2many('saas.marketplace.app', 'category_id', string='Apps')
    app_count = fields.Integer(string='Apps', compute='_compute_app_count')

    @api.depends('app_ids')
    def _compute_app_count(self):
        for rec in self:
            rec.app_count = len(rec.app_ids.filtered('active'))
