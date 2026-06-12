from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import secrets
import re
import logging

_logger = logging.getLogger(__name__)

DOMAIN_STATES = [
    ('draft', 'Draft'), ('pending_dns', 'Pending DNS'), ('dns_verified', 'DNS Verified'),
    ('ssl_pending', 'SSL Pending'), ('active', 'Active'), ('failed', 'Failed'), ('removed', 'Removed'),
]
ROUTING_TYPES = [('cname', 'CNAME'), ('a', 'A Record')]
DOMAIN_RE = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})+$')


class SaasDomain(models.Model):
    _name = 'saas.domain'
    _description = 'Custom Domain'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'domain'

    domain = fields.Char(string='Custom Domain', required=True, index=True, tracking=True)
    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade', index=True)
    state = fields.Selection(selection=DOMAIN_STATES, string='Status', default='draft',
                             required=True, tracking=True, index=True)
    is_primary = fields.Boolean(string='Primary Domain', default=False)
    verification_token = fields.Char(string='Verification Token', readonly=True, copy=False)
    txt_record_name = fields.Char(string='TXT Record Name', compute='_compute_dns_instructions')
    txt_record_value = fields.Char(string='TXT Record Value', related='verification_token')
    routing_type = fields.Selection(selection=ROUTING_TYPES, string='Routing Type', default='cname')
    routing_target = fields.Char(string='Routing Target', compute='_compute_dns_instructions')
    ssl_issued = fields.Boolean(string='SSL Issued', default=False)
    ssl_issued_at = fields.Datetime(string='SSL Issued At', readonly=True)
    ssl_expires_at = fields.Datetime(string='SSL Expires At', readonly=True)
    ssl_provider = fields.Char(string='SSL Provider', default="Let's Encrypt")
    ssl_days_left = fields.Integer(string='SSL Days Left', compute='_compute_ssl_days_left')
    last_check_at = fields.Datetime(string='Last DNS Check', readonly=True)
    check_count = fields.Integer(string='Verification Attempts', default=0)
    error_message = fields.Text(string='Last Error')
    activated_at = fields.Datetime(string='Activated At', readonly=True)
    verification_ids = fields.One2many('saas.domain.verification', 'domain_id', string='Verification Log')

    _sql_constraints = [('domain_unique', 'UNIQUE(domain)', 'This domain is already registered.')]

    @api.depends('ssl_expires_at')
    def _compute_ssl_days_left(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for rec in self:
            rec.ssl_days_left = (rec.ssl_expires_at - now).days if rec.ssl_expires_at else 0

    @api.depends('domain', 'verification_token', 'routing_type', 'tenant_id')
    def _compute_dns_instructions(self):
        config = self.env['saas.config'].sudo()._get_config()
        platform_domain = config.platform_domain
        platform_ip = self.env['ir.config_parameter'].sudo().get_param('saas_domain.platform_ip', '129.121.98.243')
        for rec in self:
            rec.txt_record_name = f'_clickbuild-verify.{rec.domain}' if rec.domain else ''
            if rec.routing_type == 'cname' and rec.tenant_id:
                rec.routing_target = f'{rec.tenant_id.subdomain}.{platform_domain}'
            else:
                rec.routing_target = platform_ip

    @api.constrains('domain')
    def _check_domain_format(self):
        for rec in self:
            domain = (rec.domain or '').lower().strip()
            if not DOMAIN_RE.match(domain):
                raise ValidationError(_('Invalid domain format: "%s". Use e.g. erp.acme.com', rec.domain))
            config = self.env['saas.config'].sudo()._get_config()
            if domain == config.platform_domain or domain.endswith(f'.{config.platform_domain}'):
                raise ValidationError(_('You cannot map a subdomain of the platform domain.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('domain'):
                vals['domain'] = vals['domain'].lower().strip()
            if not vals.get('verification_token'):
                vals['verification_token'] = self._generate_token()
        return super().create(vals_list)

    @staticmethod
    def _generate_token():
        return f'clickbuild-verify={secrets.token_urlsafe(24)}'

    def action_start_verification(self):
        self.ensure_one()
        if self.state not in ('draft', 'failed'):
            raise UserError(_('Domain verification already in progress.'))
        if not self.verification_token:
            self.verification_token = self._generate_token()
        self.write({'state': 'pending_dns', 'error_message': False})
        return self.action_check_dns()

    def action_check_dns(self):
        self.ensure_one()
        from odoo.addons.saas_domain_manager.services.domain_service import DomainService
        return DomainService(self.env).verify_domain(self)

    def action_remove(self):
        self.ensure_one()
        from odoo.addons.saas_domain_manager.services.domain_service import DomainService
        DomainService(self.env).remove_domain(self)

    def action_retry(self):
        self.ensure_one()
        self.write({'state': 'draft', 'error_message': False, 'check_count': 0})
        return self.action_start_verification()

    def action_set_primary(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active domains can be set as primary.'))
        self.search([('tenant_id', '=', self.tenant_id.id), ('id', '!=', self.id)]).write({'is_primary': False})
        self.is_primary = True
        self.tenant_id.sudo().with_context(bypass_fsm=True).write({'custom_domain': self.domain})

    @api.model
    def cron_verify_pending(self):
        from odoo.addons.saas_domain_manager.services.domain_service import DomainService
        DomainService(self.env).cron_verify_pending()

    @api.model
    def cron_renew_ssl(self):
        from odoo.addons.saas_domain_manager.services.domain_service import DomainService
        DomainService(self.env).cron_renew_ssl()
