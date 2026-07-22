from odoo import fields, models


class SaasTenant(models.Model):
    _inherit = 'saas.tenant'

    is_demo = fields.Boolean(string='Enterprise Demo', default=False, index=True, copy=False)
    demo_request_id = fields.Many2one(
        'saas.demo.request', string='Demo Request', readonly=True, copy=False,
        ondelete='set null')
    demo_template_id = fields.Many2one(
        'saas.demo.template', string='Demo Template', readonly=True, copy=False,
        ondelete='set null')
    demo_expires_at = fields.Datetime(string='Demo Expires At', readonly=True, copy=False)
    demo_module_codes = fields.Text(string='Demo Applications', readonly=True, copy=False)
    demo_sandbox_state = fields.Selection([
        ('pending', 'Pending'), ('enforced', 'Enforced'), ('failed', 'Failed'),
    ], string='Demo Sandbox', default='pending', readonly=True, copy=False)

    def write(self, vals):
        result = super().write(vals)
        # The host provisioner writes the final database name only after the
        # database, filestore, tenant identity, and HTTPS request are ready.
        # This is a safer readiness signal than the early lead -> trial change.
        final_instance = vals.get('api_instance_id')
        if final_instance and not str(final_instance).startswith('pending:'):
            for tenant in self.filtered(lambda item: item.is_demo and item.demo_request_id):
                request = tenant.demo_request_id
                if request.state in ('queued', 'provisioning'):
                    request._set_state(
                        'ready',
                        expires_at=request.expires_at or tenant.demo_expires_at,
                        health_status='pending')
        return result
