from odoo import api, fields, models


class SaasTenant(models.Model):
    _inherit = 'saas.tenant'

    # Billable Odoo Enterprise seats for this tenant (0 for community).
    odoo_license_seats = fields.Integer(
        string='Odoo License Seats', compute='_compute_odoo_license',
        store=True, help='Enterprise seats this tenant consumes on your Odoo '
                         'subscription (its purchased seats).')
    odoo_license_cost = fields.Float(
        string='Odoo License Cost / Month', digits=(10, 2),
        compute='_compute_odoo_license', store=True,
        help='What you owe Odoo per month for this tenant '
             '(seats × wholesale cost per user).')

    @api.depends('edition', 'user_count', 'state',
                 'plan_id', 'plan_id.max_users', 'plan_id.enterprise_license_cost_per_user')
    def _compute_odoo_license(self):
        for rec in self:
            if rec.edition == 'enterprise' and rec.state not in ('deleted', 'lead', 'cancelled', 'archived'):
                seats = rec.user_count or (rec.plan_id.max_users if rec.plan_id else 0) or 0
                cost_per = rec.plan_id.enterprise_license_cost_per_user if rec.plan_id else 0.0
                rec.odoo_license_seats = seats
                rec.odoo_license_cost = round(seats * cost_per, 2)
            else:
                rec.odoo_license_seats = 0
                rec.odoo_license_cost = 0.0
