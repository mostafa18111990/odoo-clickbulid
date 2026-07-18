from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaasTenant(models.Model):
    _inherit = 'saas.tenant'

    # Empty = hosted on this platform's local server (default). Set = the
    # tenant is provisioned and managed on the customer's external server
    # over SSH by the remote provisioning service.
    external_server_id = fields.Many2one(
        'saas.external.server', string='External Server', index=True,
        ondelete='restrict', copy=False, groups='saas_core.group_saas_super_admin',
        help='Leave empty to host on the ClickBuild platform server. '
             'Choose a server to provision this tenant on the customer\'s '
             'own infrastructure over SSH.')
    hosting_type = fields.Selection(
        [('platform', 'Platform Infrastructure'), ('dedicated', 'Dedicated Customer Server')],
        string='Hosting Type', default='platform', required=True, copy=False,
        groups='saas_core.group_saas_super_admin')
    is_remote = fields.Boolean(compute='_compute_is_remote', store=True,
                               string='Remote-hosted',
                               groups='saas_core.group_saas_super_admin')

    @api.depends('external_server_id')
    def _compute_is_remote(self):
        for rec in self:
            rec.is_remote = bool(rec.external_server_id)

    @api.constrains('hosting_type', 'external_server_id')
    def _check_hosting_target(self):
        for rec in self:
            if rec.hosting_type == 'dedicated' and not rec.external_server_id:
                raise UserError(_('Choose the dedicated server for this tenant.'))
            if rec.hosting_type == 'platform' and rec.external_server_id:
                raise UserError(_('Platform-hosted tenants cannot have an external server.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('external_server_id'):
                vals['hosting_type'] = 'dedicated'
        return super().create(vals_list)

    def write(self, vals):
        target_change = {'hosting_type', 'external_server_id'} & set(vals)
        if target_change and not self.env.user.has_group('saas_core.group_saas_super_admin'):
            raise UserError(_('Only SaaS Super Admins may change a tenant hosting target.'))
        if target_change and not self.env.context.get('allow_hosting_migration'):
            for rec in self:
                if rec.api_instance_id or rec.state not in ('lead',):
                    new_server = vals.get('external_server_id', rec.external_server_id.id)
                    new_type = vals.get('hosting_type', rec.hosting_type)
                    if new_server != rec.external_server_id.id or new_type != rec.hosting_type:
                        raise UserError(_(
                            'The hosting target is locked after provisioning. Use the controlled '
                            'server migration process instead.'))
        vals = dict(vals)
        if vals.get('external_server_id'):
            vals['hosting_type'] = 'dedicated'
        elif vals.get('hosting_type') == 'platform':
            vals['external_server_id'] = False
        return super().write(vals)
