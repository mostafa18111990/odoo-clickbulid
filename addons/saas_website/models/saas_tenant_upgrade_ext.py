from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaasTenantUpgradeExt(models.Model):
    """Extend saas.tenant with upgrade functionality."""
    _inherit = 'saas.tenant'

    upgrade_ids = fields.One2many('saas.tenant.upgrade', 'tenant_id', string='Upgrade Requests')
    upgrade_count = fields.Integer('Upgrade Count', compute='_compute_upgrade_count')
    last_upgraded_date = fields.Datetime('Last Upgraded', readonly=True)
    upgradeable = fields.Boolean('Can Upgrade', compute='_compute_upgradeable')

    @api.depends('upgrade_ids')
    def _compute_upgrade_count(self):
        for tenant in self:
            tenant.upgrade_count = len(tenant.upgrade_ids)

    @api.depends('edition', 'state')
    def _compute_upgradeable(self):
        for tenant in self:
            # Can only upgrade from community to enterprise
            can_upgrade = (
                tenant.edition == 'community' and
                tenant.state in ['trial', 'active']
            )
            tenant.upgradeable = can_upgrade

    def action_request_upgrade(self):
        """Customer requests upgrade from Community to Enterprise."""
        from odoo.addons.saas_website.services.tenant_upgrade_service import TenantUpgradeService

        for tenant in self:
            if tenant.edition == 'enterprise':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'info',
                        'message': _('Already on Enterprise Edition'),
                    }
                }

            service = TenantUpgradeService(self.env)
            can_upgrade, error = service.can_upgrade(tenant)

            if not can_upgrade:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'warning',
                        'message': error,
                    }
                }

            # Find enterprise plan
            enterprise_plan = self.env['saas.plan'].search([
                ('edition', '=', 'enterprise'),
                ('active', '=', True)
            ], limit=1)

            if not enterprise_plan:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'warning',
                        'message': _('Enterprise plan not available'),
                    }
                }

            result = service.create_upgrade_request(tenant.id, enterprise_plan.id)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _('Upgrade request submitted! Admin will review shortly.'),
                }
            }

    def action_admin_upgrade(self):
        """Open upgrade wizard for admin."""
        for tenant in self:
            return {
                'name': _('Upgrade Tenant to Enterprise'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'saas.tenant.upgrade.wizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': {
                    'default_tenant_id': tenant.id,
                    'default_from_edition': tenant.edition,
                }
            }

    def action_view_upgrades(self):
        """View upgrade history for this tenant."""
        self.ensure_one()
        return {
            'name': _('Upgrade History'),
            'view_type': 'tree,form',
            'view_mode': 'tree,form',
            'res_model': 'saas.tenant.upgrade',
            'type': 'ir.actions.act_window',
            'domain': [('tenant_id', '=', self.id)],
        }
