from odoo import api, fields, models


class SaasTenant(models.Model):
    _inherit = 'saas.tenant'

    # Empty = hosted on this platform's local server (default). Set = the
    # tenant is provisioned and managed on the customer's external server
    # over SSH by the remote provisioning service.
    external_server_id = fields.Many2one(
        'saas.external.server', string='External Server', index=True,
        ondelete='restrict', copy=False,
        help='Leave empty to host on the ClickBuild platform server. '
             'Choose a server to provision this tenant on the customer\'s '
             'own infrastructure over SSH.')
    is_remote = fields.Boolean(compute='_compute_is_remote', store=True,
                               string='Remote-hosted')

    @api.depends('external_server_id')
    def _compute_is_remote(self):
        for rec in self:
            rec.is_remote = bool(rec.external_server_id)
