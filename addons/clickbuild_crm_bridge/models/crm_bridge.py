import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ClickBuildCrmFollowupRule(models.Model):
    _name = 'clickbuild.crm.followup.rule'
    _description = 'ClickBuild CRM Follow-up Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    trigger = fields.Selection([
        ('contact_new', 'Website Inquiry Received'),
        ('demo_requested', 'Enterprise Demo Requested'),
        ('demo_delivered', 'Enterprise Demo Delivered'),
    ], required=True, index=True)
    sequence = fields.Integer(default=10)
    delay_days = fields.Integer(default=1, required=True)
    activity_type_id = fields.Many2one(
        'mail.activity.type', required=True,
        default=lambda self: self.env.ref('mail.mail_activity_data_todo'))
    user_id = fields.Many2one('res.users', domain=[('share', '=', False)])
    summary = fields.Char(required=True, translate=True)
    note = fields.Html(translate=True, sanitize=True)
    active = fields.Boolean(default=True, index=True)

    _nonnegative_delay = models.Constraint(
        'CHECK(delay_days >= 0)', 'Follow-up delay cannot be negative.')


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    clickbuild_origin = fields.Selection([
        ('contact', 'Website Contact'), ('demo', 'Enterprise Demo')], index=True)
    clickbuild_website_lead_id = fields.Many2one(
        'saas.website.lead', ondelete='set null', index=True, copy=False)
    clickbuild_demo_request_id = fields.Many2one(
        'saas.demo.request', ondelete='set null', index=True, copy=False)
    clickbuild_privacy_consent = fields.Boolean(copy=False)
    clickbuild_consent_at = fields.Datetime(copy=False)
    clickbuild_landing_page = fields.Char(copy=False)
    clickbuild_referrer = fields.Char(copy=False)
    clickbuild_utm_term = fields.Char(copy=False)
    clickbuild_utm_content = fields.Char(copy=False)

    def _clickbuild_apply_followup(self, trigger):
        model_id = self.env['ir.model']._get_id('crm.lead')
        rules = self.env['clickbuild.crm.followup.rule'].sudo().search([
            ('trigger', '=', trigger), ('active', '=', True)])
        for lead in self.sudo():
            for rule in rules:
                existing = self.env['mail.activity'].sudo().search_count([
                    ('res_model_id', '=', model_id), ('res_id', '=', lead.id),
                    ('summary', '=', rule.summary),
                ])
                if existing:
                    continue
                user = rule.user_id or lead.user_id or self.env.ref('base.user_admin')
                self.env['mail.activity'].sudo().create({
                    'activity_type_id': rule.activity_type_id.id,
                    'res_model_id': model_id,
                    'res_id': lead.id,
                    'user_id': user.id,
                    'summary': rule.summary,
                    'note': rule.note,
                    'date_deadline': fields.Date.context_today(lead) + timedelta(days=rule.delay_days),
                })
        return True


class ClickBuildCrmBridgeMixin(models.AbstractModel):
    _name = 'clickbuild.crm.bridge.mixin'
    _description = 'ClickBuild CRM Bridge Mixin'

    @api.model
    def _clickbuild_stage(self, name, sequence):
        stage = self.env['crm.stage'].sudo().search([('name', '=', name)], limit=1)
        return stage or self.env['crm.stage'].sudo().create({
            'name': name, 'sequence': sequence})

    @api.model
    def _clickbuild_utm(self, model, name):
        name = (name or '').strip()[:240]
        if not name:
            return False
        record = self.env[model].sudo().search([('name', '=ilike', name)], limit=1)
        return record or self.env[model].sudo().create({'name': name})

    def _clickbuild_crm_values(self, origin):
        self.ensure_one()
        if origin == 'demo':
            description = '\n'.join(filter(None, [
                self.notes,
                'Requested applications: %s' % self.requested_apps if self.requested_apps else '',
                'Sector: %s' % self.sector,
                'Users: %s; Branches: %s' % (self.user_count, self.branch_count),
            ]))
            return {
                'name': 'Enterprise Demo — %s' % self.company_name,
                'contact_name': self.contact_name,
                'partner_name': self.company_name,
                'email_from': self.email,
                'phone': self.phone,
                'description': description,
                'clickbuild_origin': 'demo',
                'clickbuild_demo_request_id': self.id,
                'clickbuild_privacy_consent': self.privacy_consent,
                'clickbuild_consent_at': self.consent_at,
                'clickbuild_landing_page': self.landing_url,
                'clickbuild_referrer': self.referrer_url,
                'clickbuild_utm_term': self.utm_term,
                'clickbuild_utm_content': self.utm_content,
                'stage_id': self._clickbuild_stage('Demo Requested', 30).id,
            }
        return {
            'name': '%s — %s' % (self.requested_service or 'Website inquiry', self.company or self.name),
            'contact_name': self.name,
            'partner_name': self.company,
            'email_from': self.email,
            'phone': self.phone,
            'description': self.message,
            'clickbuild_origin': 'contact',
            'clickbuild_website_lead_id': self.id,
            'clickbuild_privacy_consent': self.privacy_consent,
            'clickbuild_consent_at': self.consent_at,
            'clickbuild_landing_page': self.landing_page,
            'clickbuild_referrer': self.referrer,
            'clickbuild_utm_term': self.utm_term,
            'clickbuild_utm_content': self.utm_content,
            'stage_id': self._clickbuild_stage('New', 10).id,
        }

    def _clickbuild_sync_crm(self, origin):
        for record in self.sudo():
            if not record.privacy_consent:
                continue
            crm_lead = record.crm_lead_id
            values = record._clickbuild_crm_values(origin)
            source = self._clickbuild_utm('utm.source', record.utm_source)
            medium = self._clickbuild_utm('utm.medium', record.utm_medium)
            campaign = self._clickbuild_utm('utm.campaign', record.utm_campaign)
            values.update({
                'source_id': source.id if source else False,
                'medium_id': medium.id if medium else False,
                'campaign_id': campaign.id if campaign else False,
            })
            try:
                if crm_lead:
                    crm_lead.sudo().write(values)
                else:
                    crm_lead = self.env['crm.lead'].sudo().create(values)
                    record.sudo().write({'crm_lead_id': crm_lead.id})
                crm_lead._clickbuild_apply_followup(
                    'demo_requested' if origin == 'demo' else 'contact_new')
            except Exception:
                _logger.exception('CRM bridge failed for %s,%s', record._name, record.id)
        return True


class SaasWebsiteLead(models.Model):
    _name = 'saas.website.lead'
    _inherit = ['saas.website.lead', 'clickbuild.crm.bridge.mixin']

    crm_lead_id = fields.Many2one('crm.lead', readonly=True, copy=False, index=True)
    privacy_consent = fields.Boolean(default=False, copy=False)
    consent_at = fields.Datetime(copy=False)
    utm_term = fields.Char()
    utm_content = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clickbuild_sync_crm('contact')
        return records


class SaasDemoRequest(models.Model):
    _name = 'saas.demo.request'
    _inherit = ['saas.demo.request', 'clickbuild.crm.bridge.mixin']

    crm_lead_id = fields.Many2one('crm.lead', readonly=True, copy=False, index=True)
    consent_at = fields.Datetime(copy=False)
    utm_term = fields.Char()
    utm_content = fields.Char()
    referrer_url = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clickbuild_sync_crm('demo')
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals and vals['state'] in ('ready', 'active', 'extended'):
            stage = self._clickbuild_stage('Demo Delivered', 40)
            crm_leads = self.filtered('crm_lead_id').mapped('crm_lead_id').sudo()
            crm_leads.write({'stage_id': stage.id})
            crm_leads._clickbuild_apply_followup('demo_delivered')
        return result
