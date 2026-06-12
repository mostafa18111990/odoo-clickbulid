from odoo import models, fields


class SaasReferralProgram(models.Model):
    _name = 'saas.referral.program'
    _description = 'Referral Program Settings'

    name = fields.Char(string='Name', required=True, default='Default Referral Program')
    active = fields.Boolean(default=True)
    referrer_reward_type = fields.Selection(
        selection=[('credit', 'Account Credit'), ('cash', 'Cash Payout'),
                   ('discount', 'Discount Coupon')],
        string='Referrer Reward', default='credit', required=True)
    referrer_reward_value = fields.Float(string='Referrer Reward Value', default=50.0)
    referee_discount_percent = fields.Float(string='New Customer Discount %', default=10.0)
    minimum_paid_amount = fields.Float(string='Min Paid By Referee', default=0.0,
                                       help='Reward only after referee pays this amount')
    expiry_days = fields.Integer(string='Referral Code Expiry (days)', default=90)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
