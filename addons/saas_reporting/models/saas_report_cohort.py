from odoo import models, fields


class SaasReportCohort(models.Model):
    _name = 'saas.report.cohort'
    _description = 'SaaS Cohort Retention'
    _order = 'cohort_month desc, month_offset'

    cohort_month = fields.Date(string='Cohort Month', required=True, index=True)
    month_offset = fields.Integer(string='Month Offset', required=True, index=True,
                                  help='0=signup month, 1=one month later, etc.')
    cohort_size = fields.Integer(string='Cohort Size')
    retained = fields.Integer(string='Retained')
    retention_pct = fields.Float(string='Retention %', digits=(5, 2))
    revenue_retained = fields.Monetary(string='Revenue Retained',
                                       currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)

    _sql_constraints = [('cohort_offset_unique',
                         'UNIQUE(cohort_month, month_offset)',
                         'One row per cohort/offset.')]
