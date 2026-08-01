from odoo import fields


def post_init_hook(env):
    # Stages are idempotent and do not alter existing CRM opportunities.
    bridge = env['clickbuild.crm.bridge.mixin']
    for name, sequence in [
        ('New', 10), ('Qualified', 20), ('Demo Requested', 30),
        ('Demo Delivered', 40), ('Quotation', 50), ('Negotiation', 60),
    ]:
        bridge._clickbuild_stage(name, sequence)

    WebsiteLead = env['saas.website.lead'].sudo()
    WebsiteLead.search([('privacy_consent', '=', True), ('crm_lead_id', '=', False)])._clickbuild_sync_crm('contact')
    Demo = env['saas.demo.request'].sudo()
    Demo.search([('privacy_consent', '=', True), ('crm_lead_id', '=', False)])._clickbuild_sync_crm('demo')
    env.cr.commit()
