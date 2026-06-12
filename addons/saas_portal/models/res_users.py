from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    saas_tenant_id = fields.Many2one('saas.tenant', string='SaaS Tenant', ondelete='set null', index=True)
    is_saas_customer = fields.Boolean(string='Is SaaS Customer', compute='_compute_is_saas_customer', store=True)

    @api.depends('saas_tenant_id')
    def _compute_is_saas_customer(self):
        for user in self:
            user.is_saas_customer = bool(user.saas_tenant_id)

    def get_my_tenant(self):
        self.ensure_one()
        return self.saas_tenant_id
