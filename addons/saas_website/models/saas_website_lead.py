from odoo import models, fields, api

LEAD_SOURCES = [
    ('contact_form', 'Contact Form'), ('newsletter', 'Newsletter'),
    ('demo_request', 'Demo Request'), ('pricing_page', 'Pricing Page'),
    ('chat', 'Live Chat'), ('other', 'Other'),
]
LEAD_STATES = [
    ('new', 'New'), ('contacted', 'Contacted'), ('qualified', 'Qualified'),
    ('converted', 'Converted to Tenant'), ('lost', 'Lost'),
]


class SaasWebsiteLead(models.Model):
    _name = 'saas.website.lead'
    _description = 'Website Lead'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True, index=True)
    phone = fields.Char(string='Phone')
    company = fields.Char(string='Company')
    message = fields.Text(string='Message')
    source = fields.Selection(selection=LEAD_SOURCES, string='Source', default='contact_form', index=True)
    state = fields.Selection(selection=LEAD_STATES, string='Status', default='new', tracking=True, index=True)
    utm_source = fields.Char(string='UTM Source')
    utm_medium = fields.Char(string='UTM Medium')
    utm_campaign = fields.Char(string='UTM Campaign')
    referrer = fields.Char(string='Referrer URL')
    landing_page = fields.Char(string='Landing Page')
    interested_plan_id = fields.Many2one('saas.plan', string='Interested Plan')
    country = fields.Char(string='Country')
    language = fields.Selection(selection=[('ar', 'Arabic'), ('en', 'English')], string='Language', default='ar')
    converted_tenant_id = fields.Many2one('saas.tenant', string='Converted Tenant', ondelete='set null')
    newsletter_opt_in = fields.Boolean(string='Newsletter Opt-in', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead in leads:
            try:
                self.env['saas.event']._publish(event_type='tenant.lead.created',
                    model='saas.website.lead', record_id=lead.id,
                    payload={'lead_id': lead.id, 'email': lead.email, 'source': lead.source,
                             'plan': lead.interested_plan_id.code if lead.interested_plan_id else ''})
            except Exception:
                pass
        return leads

    def action_mark_converted(self, tenant):
        self.write({'state': 'converted', 'converted_tenant_id': tenant.id})
