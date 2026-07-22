from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


SECTOR_SELECTION = [
    ('construction', 'Construction'),
    ('trading-distribution', 'Trading & Distribution'),
    ('retail', 'Retail'),
    ('restaurants-cafes', 'Restaurants & Cafes'),
    ('manufacturing', 'Manufacturing'),
    ('professional-services', 'Professional Services'),
    ('real-estate', 'Real Estate & Property Management'),
    ('ecommerce', 'eCommerce'),
    ('field-services', 'Maintenance & Field Services'),
    ('education', 'Education & Training'),
    ('startups-smes', 'Startups & SMEs'),
]


class SaasDemoTemplate(models.Model):
    _name = 'saas.demo.template'
    _description = 'Enterprise Sector Demo Template'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    sector = fields.Selection(SECTOR_SELECTION, required=True, index=True)
    edition = fields.Selection(
        [('enterprise', 'Enterprise')], default='enterprise', required=True,
        readonly=True)
    module_codes = fields.Text(
        string='Enterprise Applications', required=True,
        help='Comma-separated technical module names installed in this demo template.')
    default_duration_days = fields.Integer(default=14, required=True)
    default_user_count = fields.Integer(default=5, required=True)
    sample_scenario = fields.Text(translate=True)
    pool_target = fields.Integer(
        string='Ready Database Target', default=1,
        help='Desired number of sanitized ready databases for this sector.')

    _sector_unique = models.Constraint(
        'UNIQUE(sector)', 'Only one Enterprise demo template is allowed per sector.')

    @api.constrains('edition', 'default_duration_days', 'default_user_count', 'pool_target')
    def _check_enterprise_template(self):
        for record in self:
            if record.edition != 'enterprise':
                raise ValidationError(_('Demo templates must use Odoo Enterprise.'))
            if record.default_duration_days < 1 or record.default_duration_days > 30:
                raise ValidationError(_('Demo duration must be between 1 and 30 days.'))
            if record.default_user_count < 1 or record.default_user_count > 100:
                raise ValidationError(_('Demo users must be between 1 and 100.'))
            if record.pool_target < 0 or record.pool_target > 20:
                raise ValidationError(_('Ready database target must be between 0 and 20.'))
