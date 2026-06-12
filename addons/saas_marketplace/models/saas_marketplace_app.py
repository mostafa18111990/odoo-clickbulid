from odoo import models, fields, api
from odoo.exceptions import ValidationError

PRICING_MODELS = [
    ('free', 'Free'), ('monthly', 'Monthly Subscription'),
    ('yearly', 'Yearly Subscription'), ('one_time', 'One-Time Fee'),
]


class SaasMarketplaceApp(models.Model):
    _name = 'saas.marketplace.app'
    _description = 'Marketplace App'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='App Name', required=True, translate=True)
    name_ar = fields.Char(string='الاسم بالعربية')
    code = fields.Char(string='Code', required=True, index=True)
    technical_module = fields.Char(string='Odoo Module', required=True)
    short_description = fields.Char(string='Short Description', translate=True)
    description = fields.Html(string='Full Description', translate=True)
    icon = fields.Char(string='Icon', default='fa-puzzle-piece')
    category_id = fields.Many2one('saas.marketplace.category', string='Category',
                                  required=True, ondelete='restrict', index=True)
    pricing_model = fields.Selection(selection=PRICING_MODELS, string='Pricing',
                                     default='free', required=True)
    price = fields.Float(string='Price (SAR)', digits=(10, 2), default=0.0)
    setup_fee = fields.Float(string='Setup Fee (SAR)', digits=(10, 2), default=0.0)
    price_label = fields.Char(string='Price Label', compute='_compute_price_label')
    min_plan_id = fields.Many2one('saas.plan', string='Minimum Plan')
    dependency_app_ids = fields.Many2many('saas.marketplace.app', 'saas_app_dependency_rel',
                                          'app_id', 'dependency_id', string='Required Apps')
    is_featured = fields.Boolean(string='Featured', default=False)
    is_popular = fields.Boolean(string='Popular', default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    screenshot_url = fields.Char(string='Screenshot URL')
    install_count = fields.Integer(string='Installs', compute='_compute_install_count')

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'App code must be unique.')]

    @api.depends('pricing_model', 'price')
    def _compute_price_label(self):
        for rec in self:
            if rec.pricing_model == 'free':
                rec.price_label = 'Free'
            elif rec.pricing_model == 'monthly':
                rec.price_label = f'{rec.price:.0f} SAR/mo'
            elif rec.pricing_model == 'yearly':
                rec.price_label = f'{rec.price:.0f} SAR/yr'
            else:
                rec.price_label = f'{rec.price:.0f} SAR'

    def _compute_install_count(self):
        for rec in self:
            rec.install_count = self.env['saas.tenant.app'].search_count([
                ('app_id', '=', rec.id), ('state', '=', 'installed')])

    @api.constrains('price', 'pricing_model')
    def _check_price(self):
        for rec in self:
            if rec.pricing_model != 'free' and rec.price <= 0:
                raise ValidationError(f'App "{rec.name}": paid apps must have a price > 0.')

    def is_eligible_for_tenant(self, tenant):
        self.ensure_one()
        if self.min_plan_id:
            tenant_price = tenant.plan_id.monthly_price if tenant.plan_id else 0
            if tenant_price < self.min_plan_id.monthly_price:
                return False, f'Requires {self.min_plan_id.name} plan or higher'
        for dep in self.dependency_app_ids:
            installed = self.env['saas.tenant.app'].search_count([
                ('tenant_id', '=', tenant.id), ('app_id', '=', dep.id), ('state', '=', 'installed')])
            if not installed:
                return False, f'Requires "{dep.name}" to be installed first'
        return True, ''
