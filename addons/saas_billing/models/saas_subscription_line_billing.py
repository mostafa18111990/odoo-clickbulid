from odoo import models, fields


class SaasSubscriptionLineBilling(models.Model):
    _name = 'saas.subscription.line'
    _inherit = 'saas.subscription.line'

    # invoice_id was deferred in saas_subscription (saas.invoice did not exist yet);
    # billing module adds the link now.
    invoice_id = fields.Many2one('saas.invoice', string='Invoice', ondelete='set null')
