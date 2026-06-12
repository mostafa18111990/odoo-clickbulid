from odoo import models, fields, api


class SaasReportSnapshot(models.Model):
    _name = 'saas.report.snapshot'
    _description = 'SaaS Daily Metrics Snapshot'
    _order = 'snapshot_date desc'
    _rec_name = 'snapshot_date'

    snapshot_date = fields.Date(string='Date', required=True, index=True,
                                default=fields.Date.today)
    mrr = fields.Monetary(string='MRR', currency_field='currency_id')
    arr = fields.Monetary(string='ARR', currency_field='currency_id')
    new_mrr = fields.Monetary(string='New MRR', currency_field='currency_id')
    expansion_mrr = fields.Monetary(string='Expansion MRR', currency_field='currency_id')
    contraction_mrr = fields.Monetary(string='Contraction MRR', currency_field='currency_id')
    churned_mrr = fields.Monetary(string='Churned MRR', currency_field='currency_id')
    net_mrr_movement = fields.Monetary(string='Net MRR Movement',
                                       currency_field='currency_id', compute='_compute_net_mrr', store=True)
    active_subscriptions = fields.Integer(string='Active Subs')
    trial_subscriptions = fields.Integer(string='Trial Subs')
    paying_customers = fields.Integer(string='Paying Customers')
    new_signups = fields.Integer(string='New Signups')
    churned_customers = fields.Integer(string='Churned Customers')
    arpu = fields.Monetary(string='ARPU', currency_field='currency_id',
                           compute='_compute_arpu', store=True)
    ltv = fields.Monetary(string='LTV (estimated)', currency_field='currency_id',
                          compute='_compute_ltv', store=True)
    churn_rate = fields.Float(string='Churn Rate %', digits=(5, 2))
    gross_revenue = fields.Monetary(string='Gross Revenue', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Notes')

    _sql_constraints = [('date_unique', 'UNIQUE(snapshot_date)',
                         'Only one snapshot per date.')]

    @api.depends('new_mrr', 'expansion_mrr', 'contraction_mrr', 'churned_mrr')
    def _compute_net_mrr(self):
        for r in self:
            r.net_mrr_movement = (r.new_mrr or 0) + (r.expansion_mrr or 0) \
                - (r.contraction_mrr or 0) - (r.churned_mrr or 0)

    @api.depends('mrr', 'paying_customers')
    def _compute_arpu(self):
        for r in self:
            r.arpu = (r.mrr / r.paying_customers) if r.paying_customers else 0.0

    @api.depends('arpu', 'churn_rate')
    def _compute_ltv(self):
        for r in self:
            if r.churn_rate and r.churn_rate > 0:
                r.ltv = (r.arpu * 100.0) / r.churn_rate
            else:
                r.ltv = r.arpu * 12

    @api.model
    def cron_daily_snapshot(self):
        from odoo.addons.saas_reporting.services.reporting_service import ReportingService
        ReportingService(self.env).snapshot_today()
