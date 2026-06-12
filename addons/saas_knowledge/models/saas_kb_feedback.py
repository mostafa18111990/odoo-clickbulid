from odoo import models, fields


class SaasKbFeedback(models.Model):
    _name = 'saas.kb.feedback'
    _description = 'Article Feedback'
    _order = 'create_date desc'

    article_id = fields.Many2one('saas.kb.article', string='Article',
                                 required=True, ondelete='cascade', index=True)
    is_helpful = fields.Boolean(string='Helpful?')
    comment = fields.Text(string='Comment')
    user_id = fields.Many2one('res.users', string='User', ondelete='set null')
