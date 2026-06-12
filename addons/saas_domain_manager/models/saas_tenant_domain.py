from odoo import models, fields, api, _


class SaasTenantDomain(models.Model):
    _name = 'saas.tenant'
    _inherit = 'saas.tenant'

    domain_ids = fields.One2many('saas.domain', 'tenant_id', string='Custom Domains')
    domain_count = fields.Integer(string='Domains', compute='_compute_domain_count')
    active_domain_count = fields.Integer(string='Active Domains', compute='_compute_domain_count')

    @api.depends('domain_ids', 'domain_ids.state')
    def _compute_domain_count(self):
        for rec in self:
            rec.domain_count = len(rec.domain_ids)
            rec.active_domain_count = len(rec.domain_ids.filtered(lambda d: d.state == 'active'))

    def action_view_domains(self):
        self.ensure_one()
        return {'name': _('Custom Domains'), 'type': 'ir.actions.act_window', 'res_model': 'saas.domain',
                'view_mode': 'list,form', 'domain': [('tenant_id', '=', self.id)],
                'context': {'default_tenant_id': self.id}}

    def can_add_custom_domain(self):
        self.ensure_one()
        return bool(self.plan_id) and self.plan_id.code in ('business', 'enterprise')
