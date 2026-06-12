from odoo import models, fields


class SaasTenantReseller(models.Model):
    _name = 'saas.tenant'
    _inherit = 'saas.tenant'

    reseller_id = fields.Many2one('saas.reseller', string='Reseller', ondelete='set null', index=True)
