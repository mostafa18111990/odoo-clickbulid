from odoo import models, fields, api, _
from odoo.exceptions import UserError

PAYOUT_STATES = [('draft', 'Draft'), ('approved', 'Approved'),
                 ('paid', 'Paid'), ('cancelled', 'Cancelled')]


class SaasResellerPayout(models.Model):
    _name = 'saas.reseller.payout'
    _description = 'Reseller Payout'
    _order = 'create_date desc'
    _rec_name = 'number'

    number = fields.Char(string='Payout Number', readonly=True, copy=False, default='New')
    reseller_id = fields.Many2one('saas.reseller', string='Reseller', required=True,
                                  ondelete='restrict', index=True)
    state = fields.Selection(selection=PAYOUT_STATES, string='Status', default='draft',
                             required=True, tracking=True, index=True)
    amount = fields.Float(string='Amount', digits=(10, 2))
    currency = fields.Char(string='Currency', default='SAR')
    commission_ids = fields.One2many('saas.reseller.commission', 'payout_id', string='Commissions')
    period_start = fields.Date(string='Period Start')
    period_end = fields.Date(string='Period End')
    paid_date = fields.Date(string='Paid Date')
    payment_reference = fields.Char(string='Payment Reference')
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('number', 'New') == 'New':
                vals['number'] = self.env['ir.sequence'].next_by_code('saas.reseller.payout') or 'PO-001'
        return super().create(vals_list)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_mark_paid(self, reference=None):
        self.ensure_one()
        self.write({'state': 'paid', 'paid_date': fields.Date.today(),
                    'payment_reference': reference})
        self.commission_ids.write({'state': 'paid'})

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'paid':
            raise UserError(_('Cannot cancel a paid payout.'))
        self.commission_ids.write({'state': 'accrued', 'payout_id': False})
        self.write({'state': 'cancelled'})

    @api.model
    def cron_monthly_payouts(self):
        from odoo.addons.saas_reseller.services.commission_service import CommissionService
        CommissionService(self.env).cron_monthly_payouts()
