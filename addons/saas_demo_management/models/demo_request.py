import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .demo_template import SECTOR_SELECTION

_logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
SUBDOMAIN_RE = re.compile(r'[^a-z0-9-]+')
CORE_INDUSTRY = {
    'construction': 'construction', 'trading-distribution': 'trading',
    'retail': 'retail', 'restaurants-cafes': 'restaurant',
    'manufacturing': 'manufacturing', 'professional-services': 'services',
    'real-estate': 'real_estate', 'ecommerce': 'ecommerce',
    'field-services': 'services', 'education': 'education', 'startups-smes': 'other',
}


class SaasDemoRequest(models.Model):
    _name = 'saas.demo.request'
    _description = 'Enterprise Sector Demo Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(default='New', readonly=True, copy=False, index=True)
    state = fields.Selection([
        ('new', 'New'), ('pending_review', 'Pending Review'),
        ('needs_info', 'Needs Information'), ('approved', 'Approved'),
        ('queued', 'Queued for Provisioning'), ('provisioning', 'Provisioning'),
        ('ready', 'Ready'), ('active', 'Active'), ('extended', 'Extended'),
        ('expired', 'Expired'), ('converted', 'Converted'), ('rejected', 'Rejected'),
        ('failed', 'Failed'), ('suspended', 'Suspended'), ('deleted', 'Deleted'),
    ], default='new', required=True, tracking=True, index=True, copy=False)
    edition = fields.Selection(
        [('enterprise', 'Odoo Enterprise')], default='enterprise', required=True,
        readonly=True, tracking=True)
    sector = fields.Selection(SECTOR_SELECTION, required=True, tracking=True, index=True)
    template_id = fields.Many2one(
        'saas.demo.template', string='Enterprise Demo Template',
        domain="[('sector', '=', sector), ('edition', '=', 'enterprise'), ('active', '=', True)]",
        tracking=True)
    contact_name = fields.Char(required=True, tracking=True)
    company_name = fields.Char(required=True, tracking=True)
    email = fields.Char(required=True, tracking=True, index=True)
    phone = fields.Char(required=True, tracking=True)
    city = fields.Char()
    country_code = fields.Char(default='SA', required=True)
    user_count = fields.Integer(default=5, required=True, tracking=True)
    company_size = fields.Selection([
        ('micro', '1-10'), ('small', '11-50'), ('medium', '51-250'), ('large', '251+')])
    branch_count = fields.Integer(default=1)
    requested_apps = fields.Text()
    preferred_contact_channel = fields.Selection([
        ('phone', 'Phone'), ('whatsapp', 'WhatsApp'), ('email', 'Email'),
        ('meeting', 'Online Meeting')], default='phone')
    preferred_contact_time = fields.Char()
    notes = fields.Text()
    privacy_consent = fields.Boolean(required=True)
    utm_source = fields.Char()
    utm_medium = fields.Char()
    utm_campaign = fields.Char()
    landing_url = fields.Char()
    source_fingerprint = fields.Char(index=True, copy=False)
    duration_days = fields.Integer(default=14, required=True, tracking=True)
    requested_subdomain = fields.Char(copy=False, tracking=True)
    tenant_id = fields.Many2one('saas.tenant', readonly=True, copy=False, tracking=True)
    expires_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    decision_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    decision_at = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(copy=False)
    provisioning_error = fields.Text(readonly=True, copy=False)
    health_status = fields.Selection([
        ('pending', 'Pending Check'), ('healthy', 'Healthy'),
        ('warning', 'Warning'), ('failed', 'Failed'),
    ], default='pending', readonly=True, copy=False, tracking=True)
    health_checked_at = fields.Datetime(readonly=True, copy=False)
    health_summary = fields.Char(readonly=True, copy=False)
    telegram_chat_id = fields.Char(readonly=True, copy=False)
    telegram_message_id = fields.Char(readonly=True, copy=False)
    telegram_status = fields.Selection([
        ('pending', 'Pending'), ('sent', 'Sent'), ('disabled', 'Disabled'),
        ('failed', 'Failed')], default='pending', readonly=True, copy=False)
    telegram_error = fields.Char(readonly=True, copy=False)
    whatsapp_status = fields.Selection([
        ('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent'),
        ('disabled', 'Disabled'), ('failed', 'Failed'),
    ], default='pending', readonly=True, copy=False, tracking=True)
    whatsapp_message_id = fields.Char(readonly=True, copy=False)
    whatsapp_attempts = fields.Integer(default=0, readonly=True, copy=False)
    whatsapp_attempted_at = fields.Datetime(readonly=True, copy=False)
    whatsapp_sent_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    whatsapp_error = fields.Char(readonly=True, copy=False)

    _enterprise_only = models.Constraint(
        "CHECK(edition = 'enterprise')", 'Demo requests must use Odoo Enterprise.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('saas.demo.request') or 'New'
            vals['edition'] = 'enterprise'
            if vals.get('email'):
                vals['email'] = vals['email'].strip().lower()
        return super().create(vals_list)

    @api.constrains('email', 'phone', 'user_count', 'branch_count', 'duration_days',
                    'privacy_consent', 'edition')
    def _check_request_values(self):
        for record in self:
            digits = re.sub(r'\D', '', record.phone or '')
            if record.edition != 'enterprise':
                raise ValidationError(_('All demos must use Odoo Enterprise.'))
            if not EMAIL_RE.match(record.email or ''):
                raise ValidationError(_('Enter a valid email address.'))
            if len(digits) < 8 or len(digits) > 15:
                raise ValidationError(_('Enter a valid phone number.'))
            if not 1 <= record.user_count <= 100:
                raise ValidationError(_('Demo users must be between 1 and 100.'))
            if not 1 <= record.branch_count <= 1000:
                raise ValidationError(_('Branch count must be between 1 and 1000.'))
            if not 1 <= record.duration_days <= 30:
                raise ValidationError(_('Demo duration must be between 1 and 30 days.'))
            if not record.privacy_consent:
                raise ValidationError(_('Privacy consent is required.'))

    @api.onchange('sector')
    def _onchange_sector(self):
        template = self.env['saas.demo.template'].search([
            ('sector', '=', self.sector), ('active', '=', True)], limit=1)
        self.template_id = template
        if template:
            self.duration_days = template.default_duration_days
            self.user_count = template.default_user_count

    def _set_state(self, state, **extra):
        self.ensure_one()
        extra['state'] = state
        self.write(extra)
        return True

    def action_submit_for_review(self):
        for record in self.filtered(lambda r: r.state == 'new'):
            record._set_state('pending_review')
            record._notify_telegram()
        return True

    def action_approve(self):
        for record in self:
            if record.state not in ('new', 'pending_review', 'needs_info'):
                raise UserError(_('Only requests awaiting review can be approved.'))
            template = record.template_id or self.env['saas.demo.template'].search([
                ('sector', '=', record.sector), ('active', '=', True)], limit=1)
            if not template:
                raise UserError(_('Configure an Enterprise demo template for this sector first.'))
            record._set_state(
                'approved', template_id=template.id,
                duration_days=record.duration_days or template.default_duration_days,
                decision_by_id=self.env.user.id, decision_at=fields.Datetime.now())
            record.message_post(body=_('Enterprise demo request approved.'))
        return True

    def action_reject(self):
        for record in self:
            if record.state in ('ready', 'active', 'converted', 'deleted'):
                raise UserError(_('This request can no longer be rejected.'))
            record._set_state('rejected', decision_by_id=self.env.user.id,
                              decision_at=fields.Datetime.now())
            record.message_post(body=_('Enterprise demo request rejected.'))
        return True

    def action_needs_info(self):
        for record in self:
            record._set_state('needs_info')
        return True

    def _unique_subdomain(self):
        self.ensure_one()
        base = (self.requested_subdomain or self.company_name or self.contact_name or 'demo').lower()
        base = SUBDOMAIN_RE.sub('-', base).strip('-')[:35] or 'demo'
        base = base if base.startswith('demo-') else 'demo-' + base
        candidate, counter = base, 1
        Tenant = self.env['saas.tenant'].sudo()
        while Tenant.search_count([('subdomain', '=', candidate)]):
            counter += 1
            candidate = '%s-%s' % (base[:40], counter)
        return candidate

    def action_provision(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Approve the demo request before provisioning.'))
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'saas_demo.provision_enabled', 'False')
        if str(enabled).lower() not in ('true', '1', 'yes'):
            raise UserError(_('Enterprise demo provisioning is disabled in this environment.'))
        plan = self.env['saas.plan'].sudo().tier_plan_for('enterprise', self.user_count)
        if not plan or plan.edition != 'enterprise':
            raise UserError(_('No matching Enterprise plan is configured.'))
        from odoo.addons.saas_core.services.tenant_service import TenantService
        self._set_state('queued', provisioning_error=False)
        try:
            tenant = TenantService(self.env).create_lead(
                subdomain=self._unique_subdomain(), customer_name=self.contact_name,
                customer_email=self.email, plan_id=plan.id, lead_source='website',
                phone=self.phone, company_name=self.company_name, country=self.country_code,
                industry=CORE_INDUSTRY.get(self.sector, 'other'), user_count=self.user_count)
            if tenant.edition != 'enterprise':
                raise UserError(_('Provisioning guard rejected a non-Enterprise tenant.'))
            expiration = fields.Datetime.now() + timedelta(days=self.duration_days)
            tenant.sudo().with_context(bypass_fsm=True).write({
                'is_demo': True,
                'demo_request_id': self.id,
                'demo_template_id': self.template_id.id,
                'demo_expires_at': expiration,
                'demo_module_codes': self.template_id.module_codes or '',
                'demo_sandbox_state': 'pending',
            })
            self.write({'tenant_id': tenant.id, 'requested_subdomain': tenant.subdomain,
                        'state': 'provisioning'})
            result = tenant.sudo().action_provision()
            self.expires_at = expiration
            self.message_post(body=_('Enterprise provisioning queued for %s.', tenant.subdomain))
            return result
        except Exception as exc:
            _logger.exception('Enterprise demo provisioning failed for request %s', self.name)
            self.write({'state': 'failed', 'provisioning_error': str(exc)[:2000]})
            raise

    def action_mark_ready(self):
        for record in self:
            if not record.tenant_id or record.tenant_id.edition != 'enterprise':
                raise UserError(_('A valid Enterprise tenant is required.'))
            record._set_state('ready', expires_at=record.expires_at or (
                fields.Datetime.now() + timedelta(days=record.duration_days)))
        return True

    def action_mark_active(self):
        for record in self:
            if record.state not in ('ready', 'extended'):
                raise UserError(_('Only a ready demo can be activated.'))
            if record.health_status != 'healthy':
                raise UserError(_('Run a successful readiness check before activation.'))
            record._set_state('active')
        return True

    def action_refresh_health(self):
        for record in self:
            tenant = record.tenant_id
            instance = (tenant.api_instance_id or '') if tenant else ''
            if not tenant or tenant.edition != 'enterprise' or not instance or instance.startswith('pending:'):
                record.write({
                    'health_status': 'pending',
                    'health_checked_at': fields.Datetime.now(),
                    'health_summary': _('Enterprise database is not ready yet.'),
                })
                continue
            url = 'https://%s.odoo.clickbulid.com/web/login' % tenant.subdomain
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ClickBuild-Demo-Health/1.0'})
                with urllib.request.urlopen(req, timeout=12) as response:
                    status = int(response.status or 0)
                healthy = 200 <= status < 400
                sandbox_ok = tenant.demo_sandbox_state == 'enforced'
                record.write({
                    'health_status': 'healthy' if healthy and sandbox_ok else 'warning',
                    'health_checked_at': fields.Datetime.now(),
                    'health_summary': (
                        _('Login is reachable and demo sandbox is enforced.')
                        if healthy and sandbox_ok else
                        _('Login is reachable, but demo sandbox confirmation is pending.')),
                })
                if healthy and sandbox_ok:
                    record._send_whatsapp_credentials()
            except Exception as exc:
                _logger.warning('Demo health check failed for %s: %s', record.name, exc)
                record.write({
                    'health_status': 'failed',
                    'health_checked_at': fields.Datetime.now(),
                    'health_summary': _('Demo login health check failed.'),
                })
        return True

    def action_send_whatsapp_credentials(self):
        for record in self:
            if record.health_status != 'healthy':
                raise UserError(_('Run a successful readiness check before sending credentials.'))
            record._send_whatsapp_credentials(force=True)
        return True

    def action_extend(self):
        for record in self:
            if record.state not in ('ready', 'active', 'expired', 'extended'):
                raise UserError(_('Only prepared or expired demos can be extended.'))
            base = max(record.expires_at or fields.Datetime.now(), fields.Datetime.now())
            record._set_state('extended', expires_at=base + timedelta(days=7))
            if record.tenant_id:
                record.tenant_id.sudo().with_context(bypass_fsm=True).write({
                    'demo_expires_at': record.expires_at,
                })
                record.tenant_id.sudo().action_extend_trial()
        return True

    @api.model
    def cron_refresh_demo_health(self):
        records = self.search([
            ('state', 'in', ('provisioning', 'ready', 'active', 'extended')),
            ('tenant_id', '!=', False),
        ], limit=20)
        records.action_refresh_health()

    @api.model
    def cron_expire_demos(self):
        now = fields.Datetime.now()
        records = self.search([
            ('state', 'in', ('ready', 'active', 'extended')),
            ('expires_at', '!=', False), ('expires_at', '<=', now),
        ])
        for record in records:
            record._set_state('expired')
            tenant = record.tenant_id
            if tenant and tenant.state in ('trial', 'active', 'grace_period'):
                try:
                    tenant.sudo().action_suspend()
                except Exception as exc:
                    _logger.warning('Unable to suspend expired demo %s: %s', record.name, exc)
        return True

    def _whatsapp_recipient(self):
        self.ensure_one()
        digits = re.sub(r'\D', '', self.phone or '')
        if digits.startswith('00'):
            digits = digits[2:]
        if self.country_code == 'SA':
            if digits.startswith('0'):
                digits = '966' + digits[1:]
            elif len(digits) == 9 and digits.startswith('5'):
                digits = '966' + digits
        if not 8 <= len(digits) <= 15:
            raise UserError(_('The customer phone number is not valid for WhatsApp delivery.'))
        return digits

    def _whatsapp_api(self, payload):
        params = self.env['ir.config_parameter'].sudo()
        token = params.get_param('saas_demo.whatsapp_access_token') or ''
        phone_number_id = params.get_param('saas_demo.whatsapp_phone_number_id') or ''
        api_version = params.get_param('saas_demo.whatsapp_api_version') or 'v23.0'
        if not token or not phone_number_id:
            raise UserError(_('WhatsApp Cloud API credentials are not configured.'))
        if not re.fullmatch(r'v\d+\.\d+', api_version):
            raise UserError(_('The Meta Graph API version is invalid.'))
        if not phone_number_id.isdigit():
            raise UserError(_('The WhatsApp Phone Number ID is invalid.'))
        req = urllib.request.Request(
            'https://graph.facebook.com/%s/%s/messages' % (api_version, phone_number_id),
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={
                'Authorization': 'Bearer %s' % token,
                'Content-Type': 'application/json',
            })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            # Never persist Meta's response body because it may contain
            # submitted template parameters (including the one-time password).
            raise UserError(
                _('WhatsApp Cloud API rejected the request (HTTP %s).', exc.code)
            ) from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise UserError(_('WhatsApp Cloud API request failed.')) from exc
        messages = result.get('messages') or []
        message_id = messages[0].get('id') if messages else ''
        if not message_id:
            raise UserError(_('WhatsApp Cloud API did not return a message ID.'))
        return message_id

    def _whatsapp_template_payload(self):
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        template_name = params.get_param('saas_demo.whatsapp_template_name') or ''
        language = params.get_param('saas_demo.whatsapp_template_language') or 'ar'
        tenant = self.tenant_id
        if not template_name:
            raise UserError(_('The approved WhatsApp template name is not configured.'))
        if not tenant or not tenant.admin_login or not tenant.admin_password:
            raise UserError(_('Demo login credentials are not available yet.'))
        login_url = 'https://%s.odoo.clickbulid.com/web/login' % tenant.subdomain
        expiry = fields.Datetime.context_timestamp(
            self, self.expires_at or tenant.demo_expires_at or fields.Datetime.now()
        ).strftime('%Y-%m-%d')
        values = [
            self.contact_name, login_url, tenant.admin_login,
            tenant.admin_password, expiry,
        ]
        return {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': self._whatsapp_recipient(),
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language},
                'components': [{
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': value} for value in values],
                }],
            },
        }

    def _send_whatsapp_credentials(self, force=False):
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        enabled = params.get_param('saas_demo.whatsapp_enabled', 'False')
        if str(enabled).lower() not in ('true', '1', 'yes'):
            if self.whatsapp_status != 'sent':
                self.whatsapp_status = 'disabled'
            return False
        tenant = self.tenant_id
        if (self.health_status != 'healthy' or not tenant
                or tenant.demo_sandbox_state != 'enforced'):
            return False
        self.env.cr.execute(
            'SELECT id FROM saas_demo_request WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset([
            'whatsapp_status', 'whatsapp_attempts', 'whatsapp_message_id'])
        if self.whatsapp_status == 'sent' and not force:
            return True
        if self.whatsapp_attempts >= 3 and not force:
            return False
        attempts = self.whatsapp_attempts + 1
        self.write({
            'whatsapp_status': 'sending',
            'whatsapp_attempts': attempts,
            'whatsapp_attempted_at': fields.Datetime.now(),
            'whatsapp_error': False,
        })
        try:
            message_id = self._whatsapp_api(self._whatsapp_template_payload())
            self.write({
                'whatsapp_status': 'sent',
                'whatsapp_message_id': message_id,
                'whatsapp_sent_at': fields.Datetime.now(),
                'whatsapp_error': False,
            })
            self.message_post(body=_('Demo login credentials were sent by WhatsApp.'))
            return True
        except Exception as exc:
            # Store only the sanitized exception generated by this module.
            error = str(exc)[:240]
            _logger.warning(
                'WhatsApp demo delivery failed for request %s (attempt %s)',
                self.name, attempts)
            self.write({'whatsapp_status': 'failed', 'whatsapp_error': error})
            return False

    def _callback_signature(self, action):
        self.ensure_one()
        secret = self.env['ir.config_parameter'].sudo().get_param(
            'saas_demo.callback_signing_secret') or ''
        payload = '%s:%s' % (self.id, action)
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16] if secret else ''

    def verify_callback_signature(self, action, signature):
        expected = self._callback_signature(action)
        if not expected or not hmac.compare_digest(expected, signature or ''):
            return False
        # Telegram decisions are deliberately short-lived even if an old
        # message is forwarded or recovered later.
        return bool(
            self.create_date
            and self.create_date >= fields.Datetime.now() - timedelta(days=7)
        )

    def _telegram_api(self, method, payload):
        token = self.env['ir.config_parameter'].sudo().get_param(
            'saas_demo.telegram_bot_token') or ''
        if not token:
            raise UserError(_('Telegram bot token is not configured.'))
        req = urllib.request.Request(
            'https://api.telegram.org/bot%s/%s' % (token, method),
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise UserError(_('Telegram request failed.')) from exc
        if not result.get('ok'):
            raise UserError(_('Telegram rejected the request.'))
        return result.get('result') or {}

    def _telegram_text(self):
        self.ensure_one()
        sector = dict(SECTOR_SELECTION).get(self.sector, self.sector)
        return ('طلب ديمو Enterprise جديد\n\nالطلب: %s\nالعميل: %s\nالشركة: %s\n'
                'القطاع: %s\nالمستخدمون: %s\nالهاتف: %s\nالبريد: %s\nالحالة: %s') % (
            self.name, self.contact_name, self.company_name, sector, self.user_count,
            self.phone, self.email, self.state)

    def _notify_telegram(self):
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        enabled = params.get_param('saas_demo.telegram_enabled', 'False')
        chat_id = params.get_param('saas_demo.telegram_chat_id') or ''
        if str(enabled).lower() not in ('true', '1', 'yes') or not chat_id:
            self.telegram_status = 'disabled'
            return False
        buttons = [[
            {'text': '✅ موافقة', 'callback_data': 'demo:a:%s:%s' % (
                self.id, self._callback_signature('approve'))},
            {'text': '❌ رفض', 'callback_data': 'demo:r:%s:%s' % (
                self.id, self._callback_signature('reject'))},
        ], [{'text': 'ℹ️ طلب معلومات', 'callback_data': 'demo:i:%s:%s' % (
            self.id, self._callback_signature('info'))}]]
        try:
            result = self._telegram_api('sendMessage', {
                'chat_id': chat_id, 'text': self._telegram_text(),
                'reply_markup': {'inline_keyboard': buttons}})
            self.write({'telegram_status': 'sent', 'telegram_error': False,
                        'telegram_chat_id': str(result.get('chat', {}).get('id') or chat_id),
                        'telegram_message_id': str(result.get('message_id') or '')})
            return True
        except Exception as exc:
            _logger.warning('Telegram demo notification failed for %s: %s', self.name, exc)
            self.write({'telegram_status': 'failed', 'telegram_error': str(exc)[:240]})
            return False
