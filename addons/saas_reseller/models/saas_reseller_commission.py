from odoo import models, fields, api

COMMISSION_STATES = [('accrued', 'Accrued'), ('paid', 'Paid'), ('cancelled', 'Cancelled')]


class SaasResellerCommission(models.Model):
    _name = 'saas.reseller.commission'
    _description = 'Reseller Commission'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('reseller_id', 'amount')
    def _compute_display_name(self):
        for rec in self:
            r = rec.reseller_id.name if rec.reseller_id else '?'
            rec.display_name = f'{r}: {rec.amount} {rec.currency}'

    reseller_id = fields.Many2one('saas.reseller', string='Reseller', required=True,
                                  ondelete='cascade', index=True)
    tenant_id = fields.Many2one('saas.tenant', string='Customer', ondelete='set null', index=True)
    payout_id = fields.Many2one('saas.reseller.payout', string='Payout', ondelete='set null', index=True)
    payment_amount = fields.Float(string='Payment Amount', digits=(10, 2))
    commission_rate = fields.Float(string='Rate %', digits=(5, 2))
    amount = fields.Float(string='Commission', digits=(10, 2), required=True)
    currency = fields.Char(string='Currency', default='SAR')
    state = fields.Selection(selection=COMMISSION_STATES, string='Status',
                             default='accrued', required=True, index=True)
    gateway_tx_id = fields.Char(string='Source Transaction')
    accrued_date = fields.Date(string='Accrued Date', default=fields.Date.today)

    def action_cancel(self):
        self.write({'state': 'cancelled'})
