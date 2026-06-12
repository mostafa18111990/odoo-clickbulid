from odoo import models, fields

FAQ_CATEGORIES = [
    ('general', 'General'), ('pricing', 'Pricing'), ('billing', 'Billing'),
    ('technical', 'Technical'), ('security', 'Security'), ('account', 'Account'),
]


class SaasWebsiteFaq(models.Model):
    _name = 'saas.website.faq'
    _description = 'Website FAQ'
    _order = 'sequence, id'

    question = fields.Char(string='Question', required=True, translate=True)
    question_ar = fields.Char(string='السؤال')
    answer = fields.Text(string='Answer', required=True, translate=True)
    answer_ar = fields.Text(string='الإجابة')
    faq_category = fields.Selection(selection=FAQ_CATEGORIES, string='Category', default='general', index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
