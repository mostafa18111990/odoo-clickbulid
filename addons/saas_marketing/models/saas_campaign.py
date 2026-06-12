from odoo import models, fields, api


class SaasCampaign(models.Model):
    _name = 'saas.campaign'
    _description = 'Marketing Campaign'
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True)
    channel = fields.Selection(
        selection=[('email', 'Email'), ('sms', 'SMS'), ('inapp', 'In-App')],
        string='Channel', default='email', required=True)
    subject = fields.Char(string='Subject / Title')
    body = fields.Html(string='Body')
    scope = fields.Selection(
        selection=[('all', 'All Customers'), ('trial', 'Trial Users'),
                   ('active', 'Active Subscribers'), ('churned', 'Churned'),
                   ('plan', 'Specific Plan')],
        string='Audience', default='all', required=True)
    plan_id = fields.Many2one('saas.plan', string='Plan Filter')
    coupon_id = fields.Many2one('saas.coupon', string='Attached Coupon')
    scheduled_at = fields.Datetime(string='Send At')
    sent_at = fields.Datetime(string='Sent At', readonly=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('scheduled', 'Scheduled'),
                   ('sending', 'Sending'), ('sent', 'Sent'),
                   ('cancelled', 'Cancelled')],
        string='State', default='draft', required=True, index=True)
    sent_count = fields.Integer(string='Sent', readonly=True)
    open_count = fields.Integer(string='Opens', readonly=True)
    click_count = fields.Integer(string='Clicks', readonly=True)
    notes = fields.Text(string='Notes')

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_send_now(self):
        for c in self:
            c.write({'state': 'sent', 'sent_at': fields.Datetime.now()})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
