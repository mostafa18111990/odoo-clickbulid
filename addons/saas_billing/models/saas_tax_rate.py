from odoo import models, fields, api
from odoo.exceptions import ValidationError

TAX_TYPES = [('percentage', 'Percentage (%)'), ('fixed', 'Fixed Amount')]
APPLIES_TO = [('all', 'All Charges'), ('subscription', 'Subscription Only'),
              ('overage', 'Overages Only'), ('setup', 'Setup Fees Only')]
COUNTRY_CODES = [('SA', 'Saudi Arabia'), ('AE', 'UAE'), ('EG', 'Egypt'), ('KW', 'Kuwait'),
                 ('QA', 'Qatar'), ('BH', 'Bahrain'), ('OM', 'Oman'), ('JO', 'Jordan'), ('OTHER', 'Other')]


class SaasTaxRate(models.Model):
    _name = 'saas.tax.rate'
    _description = 'SaaS Tax Rate'
    _order = 'country_code, name'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'rate', 'country_code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.name} - {rec.rate}% ({rec.country_code})'

    name = fields.Char(string='Tax Name', required=True)
    name_ar = fields.Char(string='اسم الضريبة')
    code = fields.Char(string='Tax Code', required=True, index=True)
    country_code = fields.Selection(selection=COUNTRY_CODES, string='Country', required=True, index=True)
    tax_type = fields.Selection(selection=TAX_TYPES, string='Type', default='percentage', required=True)
    rate = fields.Float(string='Rate (%)', digits=(5, 2), default=0.0)
    fixed_amount = fields.Float(string='Fixed Amount', digits=(10, 2), default=0.0)
    applies_to = fields.Selection(selection=APPLIES_TO, string='Applies To', default='all')
    active = fields.Boolean(default=True)
    registration_number = fields.Char(string='Tax Registration Number')
    invoice_label = fields.Char(string='Invoice Label', default='VAT')
    invoice_label_ar = fields.Char(string='Invoice Label (AR)', default='ضريبة القيمة المضافة')

    @api.constrains('rate')
    def _check_rate(self):
        for rec in self:
            if rec.tax_type == 'percentage' and not (0 <= rec.rate <= 100):
                raise ValidationError('Tax rate must be between 0 and 100%.')

    def calculate(self, base_amount):
        self.ensure_one()
        if not self.active:
            return 0.0
        if self.tax_type == 'percentage':
            return round(base_amount * self.rate / 100, 2)
        return self.fixed_amount

    @api.model
    def get_for_country(self, country_code, applies_to='all'):
        domain = [('country_code', '=', country_code), ('active', '=', True)]
        if applies_to != 'all':
            domain += [('applies_to', 'in', [applies_to, 'all'])]
        return self.search(domain, limit=1)
