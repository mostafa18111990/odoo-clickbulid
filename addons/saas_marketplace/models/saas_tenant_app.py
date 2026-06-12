from odoo import models, fields, api, _
from odoo.exceptions import UserError

APP_STATES = [
    ('draft', 'Requested'), ('installing', 'Installing'), ('installed', 'Installed'),
    ('uninstalling', 'Uninstalling'), ('uninstalled', 'Uninstalled'), ('failed', 'Failed'),
]


class SaasTenantApp(models.Model):
    _name = 'saas.tenant.app'
    _description = 'Tenant Installed App'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('tenant_id', 'app_id')
    def _compute_display_name(self):
        for rec in self:
            t = rec.tenant_id.subdomain if rec.tenant_id else '?'
            a = rec.app_id.name if rec.app_id else '?'
            rec.display_name = f'{t} - {a}'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True,
                                ondelete='cascade', index=True)
    app_id = fields.Many2one('saas.marketplace.app', string='App', required=True,
                             ondelete='restrict', index=True)
    state = fields.Selection(selection=APP_STATES, string='Status', default='draft',
                             required=True, tracking=True, index=True)
    addon_id = fields.Many2one('saas.subscription.addon', string='Subscription Add-on',
                               ondelete='set null')
    pricing_model = fields.Selection(related='app_id.pricing_model', string='Pricing', store=False)
    is_paid = fields.Boolean(string='Paid App', compute='_compute_is_paid')

    def _compute_is_paid(self):
        for rec in self:
            rec.is_paid = rec.app_id and rec.app_id.pricing_model != 'free'
    installed_at = fields.Datetime(string='Installed At', readonly=True)
    uninstalled_at = fields.Datetime(string='Uninstalled At', readonly=True)
    error_message = fields.Text(string='Error')
    external_job_id = fields.Char(string='FastAPI Job ID')

    _sql_constraints = [('tenant_app_unique', 'UNIQUE(tenant_id, app_id)',
                         'This app is already registered for this tenant.')]

    def mark_installed(self):
        self.write({'state': 'installed', 'installed_at': fields.Datetime.now(), 'error_message': False})

    def mark_failed(self, error):
        self.write({'state': 'failed', 'error_message': error})

    def mark_uninstalled(self):
        self.write({'state': 'uninstalled', 'uninstalled_at': fields.Datetime.now()})

    def action_uninstall(self):
        self.ensure_one()
        from odoo.addons.saas_marketplace.services.marketplace_service import MarketplaceService
        MarketplaceService(self.env).uninstall_app(self)

    def action_retry_install(self):
        self.ensure_one()
        if self.state != 'failed':
            raise UserError(_('Only failed installations can be retried.'))
        from odoo.addons.saas_marketplace.services.marketplace_service import MarketplaceService
        MarketplaceService(self.env)._execute_install(self)

    @api.model
    def cron_verify_installs(self):
        from odoo.addons.saas_marketplace.services.marketplace_service import MarketplaceService
        MarketplaceService(self.env).cron_verify_installs()
