from odoo import models, api


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def get_saas_plans(self):
        return self.env['saas.plan'].sudo().search([('active', '=', True)], order='monthly_price asc')

    @api.model
    def get_saas_config(self):
        return self.env['saas.config'].sudo()._get_config()

    @api.model
    def get_featured_faqs(self, limit=8):
        return self.env['saas.website.faq'].sudo().search([('active', '=', True)], order='sequence', limit=limit)
