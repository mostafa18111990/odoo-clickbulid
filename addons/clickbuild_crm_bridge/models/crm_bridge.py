import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
            self.filtered('crm_lead_id').mapped('crm_lead_id').sudo().write({'stage_id': stage.id})
        return result
