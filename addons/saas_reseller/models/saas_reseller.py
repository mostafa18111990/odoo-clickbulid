from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

RESELLER_STATES = [
    ('pending', 'Pending Approval'), ('active', 'Active'),
    ('suspended', 'Suspended'), ('terminated', 'Terminated'),
]
COMMISSION_MODELS = [
    ('percentage', 'Percentage of Revenue'),
    ('fixed', 'Fixed per Customer/Month'),
    ('tiered', 'Tiered by Customer Count'),
]


class SaasReseller(models.Model):
    _name = 'saas.reseller'
    _description = 'SaaS Reseller'
    _inherit = ['mail.thread']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Reseller Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    state = fields.Selection(selection=RESELLER_STATES, string='Status', default='pending',
                             required=True, tracking=True, index=True)
    contact_name = fields.Char(string='Contact Name')
    contact_email = fields.Char(string='Contact Email', required=True, index=True)
    contact_phone = fields.Char(string='Contact Phone')
    country = fields.Char(string='Country')
    portal_user_id = fields.Many2one('res.users', string='Portal User', ondelete='set null', copy=False)
    is_white_label = fields.Boolean(string='White-Label', default=False)
    brand_name = fields.Char(string='Brand Name')
    brand_logo = fields.Binary(string='Brand Logo')
    brand_domain = fields.Char(string='Brand Domain')
    brand_primary_color = fields.Char(string='Primary Color', default='#6d28d9')
    commission_model = fields.Selection(selection=COMMISSION_MODELS, string='Commission Model',
                                        default='percentage', required=True)
    commission_rate = fields.Float(string='Commission Rate (%)', digits=(5, 2), default=20.0)
    commission_fixed = fields.Float(string='Fixed Commission (SAR)', digits=(10, 2), default=0.0)
    tier_json = fields.Text(string='Tier Config (JSON)')
    total_earned = fields.Float(string='Total Earned', compute='_compute_balances', digits=(10, 2))
    total_paid = fields.Float(string='Total Paid Out', compute='_compute_balances', digits=(10, 2))
    balance_due = fields.Float(string='Balance Due', compute='_compute_balances', digits=(10, 2))
    currency = fields.Char(string='Currency', default='SAR')
    tenant_ids = fields.One2many('saas.tenant', 'reseller_id', string='Customers')
    customer_count = fields.Integer(string='Customers', compute='_compute_customer_count')
    active_customer_count = fields.Integer(string='Active Customers', compute='_compute_customer_count')
    commission_ids = fields.One2many('saas.reseller.commission', 'reseller_id', string='Commissions')
    payout_ids = fields.One2many('saas.reseller.payout', 'reseller_id', string='Payouts')

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Reseller code must be unique.')]

    @api.depends('tenant_ids', 'tenant_ids.state')
    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = len(rec.tenant_ids)
            rec.active_customer_count = len(rec.tenant_ids.filtered(lambda t: t.state == 'active'))

    @api.depends('commission_ids.amount', 'commission_ids.state', 'payout_ids.amount', 'payout_ids.state')
    def _compute_balances(self):
        for rec in self:
            earned = sum(rec.commission_ids.filtered(lambda c: c.state in ('accrued', 'paid')).mapped('amount'))
            paid = sum(rec.payout_ids.filtered(lambda p: p.state == 'paid').mapped('amount'))
            rec.total_earned = round(earned, 2)
            rec.total_paid = round(paid, 2)
            rec.balance_due = round(earned - paid, 2)

    @api.constrains('commission_rate')
    def _check_rate(self):
        for rec in self:
            if not (0 <= rec.commission_rate <= 100):
                raise ValidationError('Commission rate must be 0-100%.')

    def calculate_commission(self, payment_amount):
        self.ensure_one()
        if self.state != 'active':
            return 0.0
        if self.commission_model == 'percentage':
            return round(payment_amount * self.commission_rate / 100, 2)
        elif self.commission_model == 'fixed':
            return self.commission_fixed
        elif self.commission_model == 'tiered':
            return round(payment_amount * self._get_tier_rate() / 100, 2)
        return 0.0

    def _get_tier_rate(self):
        import json
        try:
            tiers = json.loads(self.tier_json or '[]')
            count = self.active_customer_count
            applicable = self.commission_rate
            for tier in sorted(tiers, key=lambda t: t.get('min', 0)):
                if count >= tier.get('min', 0):
                    applicable = tier.get('rate', applicable)
            return applicable
        except Exception:
            return self.commission_rate

    def action_approve(self):
        for rec in self:
            rec.state = 'active'
            rec._create_portal_user()

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_terminate(self):
        self.write({'state': 'terminated'})

    def _create_portal_user(self):
        self.ensure_one()
        if self.portal_user_id or not self.contact_email:
            return
        portal_group = self.env.ref('base.group_portal')
        reseller_group = self.env.ref('saas_reseller.group_saas_reseller', raise_if_not_found=False)
        groups = [portal_group.id]
        if reseller_group:
            groups.append(reseller_group.id)
        user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': self.contact_name or self.name, 'login': self.contact_email,
            'email': self.contact_email, 'groups_id': [(6, 0, groups)]})
        self.portal_user_id = user.id
        try:
            user.action_reset_password()
        except Exception:
            pass
