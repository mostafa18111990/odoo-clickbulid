from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaasTenantUpgradeWizard(models.TransientModel):
    _name = 'saas.tenant.upgrade.wizard'
    _description = 'Tenant Upgrade Wizard'

    tenant_id = fields.Many2one('saas.tenant', 'Tenant', required=True, ondelete='cascade')
    from_edition = fields.Char('From Edition', readonly=True)
    to_edition = fields.Selection([
        ('enterprise', 'Enterprise'),
    ], string='To Edition', required=True, default='enterprise')

    from_plan_id = fields.Many2one('saas.plan', 'Current Plan', readonly=True)
    to_plan_id = fields.Many2one('saas.plan', 'New Plan', required=True,
                                 domain=[('edition', '=', 'enterprise')])

    coupon_code = fields.Char('Coupon Code (Optional)')
    price_difference = fields.Monetary('Price Difference', readonly=True)
    currency_id = fields.Many2one('res.currency', related='to_plan_id.currency_id')

    approve_immediately = fields.Boolean('Approve Immediately', default=False)

    @api.onchange('from_plan_id')
    def _onchange_from_plan(self):
        if self.from_plan_id:
            self.from_edition = self.from_plan_id.edition

    @api.onchange('to_plan_id')
    def _compute_price_difference(self):
        if self.from_plan_id and self.to_plan_id:
            self.price_difference = self.to_plan_id.monthly_price - self.from_plan_id.monthly_price

    def action_create_upgrade(self):
        """Create upgrade request."""
        from odoo.addons.saas_website.services.tenant_upgrade_service import TenantUpgradeService

        self.ensure_one()

        try:
            service = TenantUpgradeService(self.env)

            # Create upgrade
            result = service.create_upgrade_request(
                self.tenant_id.id,
                self.to_plan_id.id,
                self.coupon_code
            )

            # Auto-approve if requested
            if self.approve_immediately:
                service.approve_upgrade(result['upgrade_id'])
                message = _('Upgrade created and approved successfully!')
            else:
                message = _('Upgrade request created. Awaiting approval.')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': message,
                }
            }

        except Exception as e:
            _logger.error(f"Upgrade creation failed: {e}")
            raise UserError(_('Failed to create upgrade: %s') % str(e))

    def action_cancel(self):
        """Close wizard."""
        return {'type': 'ir.actions.act_window_close'}
