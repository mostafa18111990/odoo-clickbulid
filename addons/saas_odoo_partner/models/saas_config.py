from odoo import fields, models


class SaasConfig(models.Model):
    _inherit = 'saas.config'

    # ── Odoo partner subscription link ──────────────────────────────────────
    odoo_enterprise_code = fields.Char(
        string='Odoo Enterprise Subscription Code',
        help='Your Odoo partner Enterprise subscription code. Written into each '
             'Enterprise tenant as database.enterprise_code at provisioning so '
             'Enterprise stays licensed and users report to your Odoo contract.')
    odoo_partner_ref = fields.Char(
        string='Odoo Partner / Contract Ref',
        help='Your partner account or contract reference on odoo.com (kept for '
             'your records; Odoo offers no public API to manage it automatically).')
    odoo_enterprise_url = fields.Char(
        string='Odoo Subscription Portal URL',
        default='https://www.odoo.com/my/subscription',
        help='Quick link to your Odoo subscription portal.')
