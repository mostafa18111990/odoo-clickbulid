import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaasPlan(models.Model):
    _name = 'saas.plan'
    _description = 'SaaS Subscription Plan'
    _order = 'monthly_price asc'

    name = fields.Char(string='Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color')

    # Limits
    max_users = fields.Integer(string='Max Users', default=5)
    max_storage_mb = fields.Integer(string='Max Storage (MB)', default=1024)
    trial_days = fields.Integer(string='Trial Days', default=14)

    # Pricing
    monthly_price = fields.Float(string='Monthly Price (SAR)', digits=(10, 2))
    yearly_price = fields.Float(string='Yearly Price (SAR)', digits=(10, 2))

    # Modules allowed on this plan
    allowed_modules = fields.Text(
        string='Allowed Modules',
        help='Comma-separated list of module names to install on tenant creation'
    )

    # Description
    description = fields.Html(string='Description')
    features = fields.Text(string='Features (one per line)')

    # Stats
    tenant_count = fields.Integer(compute='_compute_tenant_count', string='Tenants')

    def _compute_tenant_count(self):
        for plan in self:
            plan.tenant_count = self.env['saas.tenant'].search_count([
                ('plan_id', '=', plan.id)
            ])

    @api.constrains('max_users')
    def _check_max_users(self):
        for plan in self:
            if plan.max_users < 1:
                raise ValidationError('Max users must be at least 1.')

    def get_modules_list(self):
        """Return list of modules to install."""
        self.ensure_one()
        if not self.allowed_modules:
            return ['base']
        mods = [m.strip() for m in self.allowed_modules.split(',') if m.strip()]
        if 'base' not in mods:
            mods.insert(0, 'base')
        return mods

    def action_view_tenants(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tenants — {self.name}',
            'res_model': 'saas.tenant',
            'view_mode': 'list,form,kanban',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
