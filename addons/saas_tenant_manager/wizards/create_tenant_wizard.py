import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..models.sector_catalog import BUSINESS_SECTOR_SELECTION

_logger = logging.getLogger(__name__)


class CreateTenantWizard(models.TransientModel):
    _name = 'create.tenant.wizard'
    _description = 'Create New Tenant Wizard'

    # Step 1: Customer
    customer_name = fields.Char(string='Customer Name', required=True)
    customer_email = fields.Char(string='Customer Email', required=True)
    company_name = fields.Char(string='Company Name', required=True)
    phone = fields.Char(string='Phone')
    business_sector = fields.Selection(
        selection=BUSINESS_SECTOR_SELECTION, string='Business Sector',
        default='general', required=True)

    # Step 2: Domain
    subdomain = fields.Char(string='Subdomain', required=True,
        help='e.g. "mycompany" for mycompany.myerp.com')
    custom_domain = fields.Char(string='Custom Domain (optional)')

    # Step 3: Plan
    plan_id = fields.Many2one('saas.plan', string='Subscription Plan', required=True)

    # Step 4: Template
    template_db = fields.Char(string='Template Database',
        help='Leave empty to create fresh installation')

    # Step 5: Admin
    admin_login = fields.Char(string='Admin Login', default='admin')
    admin_password = fields.Char(string='Admin Password', required=True)

    # Preview
    tenant_url_preview = fields.Char(
        string='Tenant URL', compute='_compute_url_preview'
    )

    @api.depends('subdomain', 'custom_domain')
    def _compute_url_preview(self):
        for w in self:
            if w.custom_domain:
                w.tenant_url_preview = f'https://{w.custom_domain}'
            elif w.subdomain:
                w.tenant_url_preview = f'https://{w.subdomain}.myerp.com'
            else:
                w.tenant_url_preview = ''

    def action_create(self):
        self.ensure_one()
        # Check subdomain not taken
        existing = self.env['saas.tenant'].search([
            ('subdomain', '=', self.subdomain)
        ])
        if existing:
            raise ValidationError(f'Subdomain "{self.subdomain}" is already taken.')

        tenant = self.env['saas.tenant'].create({
            'name': f'{self.company_name} ERP',
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'company_name': self.company_name,
            'phone': self.phone,
            'business_sector': self.business_sector,
            'subdomain': self.subdomain,
            'custom_domain': self.custom_domain,
            'plan_id': self.plan_id.id,
            'template_db': self.template_db,
            'admin_login': self.admin_login,
            'admin_password': self.admin_password,
        })

        # Provision
        tenant.action_provision()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.tenant',
            'res_id': tenant.id,
            'view_mode': 'form',
            'target': 'current',
        }
