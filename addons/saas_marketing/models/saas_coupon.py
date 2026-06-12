from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaasCoupon(models.Model):
    _name = 'saas.coupon'
    _description = 'Promotional Coupon'
    _order = 'create_date desc'
    _rec_name = 'code'

    code = fields.Char(string='Code', required=True, index=True)
    name = fields.Char(string='Description')
    discount_type = fields.Selection(
        selection=[('percent', 'Percentage'), ('fixed', 'Fixed Amount'),
                   ('trial', 'Extra Trial Days')],
        string='Discount Type', default='percent', required=True)
    discount_value = fields.Float(string='Value', required=True, default=10.0)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    valid_from = fields.Datetime(string='Valid From', default=fields.Datetime.now)
    valid_to = fields.Datetime(string='Valid To')
    max_redemptions = fields.Integer(string='Max Redemptions', default=0,
                                     help='0 = unlimited')
    redemption_count = fields.Integer(string='Redemptions', readonly=True)
    max_per_user = fields.Integer(string='Max Per User', default=1)
    plan_ids = fields.Many2many('saas.plan', string='Eligible Plans',
                                help='Empty = all plans')
    first_time_only = fields.Boolean(string='First-Time Customers Only', default=False)
    minimum_amount = fields.Float(string='Minimum Order Amount', default=0.0)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('active', 'Active'),
                   ('paused', 'Paused'), ('expired', 'Expired')],
        string='State', default='draft', required=True, index=True)
    reseller_id = fields.Many2one('saas.reseller', string='Reseller (optional)',
                                  ondelete='set null')
    notes = fields.Text(string='Internal Notes')
    redemption_ids = fields.One2many('saas.coupon.redemption', 'coupon_id',
                                     string='Redemptions')
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Coupon code must be unique.')]

    @api.constrains('discount_type', 'discount_value')
    def _check_value(self):
        for c in self:
            if c.discount_type == 'percent' and not (0 < c.discount_value <= 100):
                raise ValidationError(_('Percentage must be between 0 and 100.'))
            if c.discount_value < 0:
                raise ValidationError(_('Discount value cannot be negative.'))

    def action_activate(self):
        self.write({'state': 'active'})

    def action_pause(self):
        self.write({'state': 'paused'})

    def is_valid(self, tenant=None, plan=None, amount=0.0):
        from datetime import datetime
        self.ensure_one()
        now = fields.Datetime.now()
        if self.state != 'active':
            return False, 'Coupon not active'
        if self.valid_from and self.valid_from > now:
            return False, 'Coupon not yet valid'
        if self.valid_to and self.valid_to < now:
            return False, 'Coupon expired'
        if self.max_redemptions and self.redemption_count >= self.max_redemptions:
            return False, 'Max redemptions reached'
        if self.plan_ids and plan and plan.id not in self.plan_ids.ids:
            return False, 'Coupon not valid for this plan'
        if self.minimum_amount and amount < self.minimum_amount:
            return False, 'Order below minimum amount'
        return True, 'OK'
