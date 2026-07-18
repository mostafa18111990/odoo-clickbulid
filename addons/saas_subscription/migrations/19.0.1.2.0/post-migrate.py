from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Move trials to annual-only billing without changing paid history."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    trials = env['saas.subscription'].search([('status', '=', 'trial')])
    for subscription in trials:
        seats = subscription.tenant_id.user_count or subscription.plan_id.max_users or 1
        annual_amount = subscription.plan_id.price_for_users(seats, 'yearly')
        subscription.write({
            'billing_cycle': 'yearly',
            'base_amount': annual_amount,
        })
    env['saas.tenant'].with_context(active_test=False).search([
        ('billing_cycle', '=', 'monthly'),
    ]).write({
        'billing_cycle': 'yearly',
    })
