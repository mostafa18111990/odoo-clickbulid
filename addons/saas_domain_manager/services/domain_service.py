from odoo import fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class DomainService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_domain_manager.services.dns_verification_service import DnsVerificationService
        from odoo.addons.saas_domain_manager.services.ssl_bridge_service import SslBridgeService
        self.dns = DnsVerificationService(env)
        self.ssl = SslBridgeService(env)

    def add_domain(self, tenant, domain, routing_type='cname'):
        domain = domain.lower().strip()
        if not tenant.can_add_custom_domain():
            raise UserError(_('Custom domains are available on Business and Enterprise plans.'))
        existing = self.env['saas.domain'].search([('domain', '=', domain), ('state', '!=', 'removed')], limit=1)
        if existing:
            raise UserError(_('Domain "%s" is already registered.', domain))
        domain_rec = self.env['saas.domain'].create({'domain': domain, 'tenant_id': tenant.id,
                                                     'routing_type': routing_type, 'state': 'draft'})
        _logger.info('Custom domain added: %s for %s', domain, tenant.subdomain)
        return domain_rec

    def verify_domain(self, domain):
        domain.write({'last_check_at': fields.Datetime.now(), 'check_count': domain.check_count + 1})
        txt = self.dns.check_txt(domain.txt_record_name, domain.verification_token)
        self.env['saas.domain.verification'].log(domain, 'txt',
            'success' if txt['found'] else 'not_found', expected=domain.verification_token,
            found=', '.join(txt.get('values', [])), details=txt.get('error'))
        if not txt['found']:
            domain.write({'state': 'pending_dns', 'error_message': _(
                'TXT record not found. Add TXT: %(n)s = %(v)s',
                n=domain.txt_record_name, v=domain.verification_token)})
            return self._notify(domain, 'warning', _('TXT verification record not found yet.'))
        if domain.routing_type == 'cname':
            route = self.dns.check_cname(domain.domain, domain.routing_target)
            self.env['saas.domain.verification'].log(domain, 'cname',
                'success' if route['found'] else 'mismatch', expected=domain.routing_target,
                found=route.get('target'), details=route.get('error'))
        else:
            route = self.dns.check_a(domain.domain, domain.routing_target)
            self.env['saas.domain.verification'].log(domain, 'a',
                'success' if route['found'] else 'mismatch', expected=domain.routing_target,
                found=', '.join(route.get('ips', [])), details=route.get('error'))
        if not route['found']:
            domain.write({'state': 'pending_dns', 'error_message': _(
                'Routing record not found. Add %(t)s: %(d)s -> %(tg)s',
                t=domain.routing_type.upper(), d=domain.domain, tg=domain.routing_target)})
            return self._notify(domain, 'warning', _('TXT verified, but routing record not set yet.'))
        domain.write({'state': 'dns_verified', 'error_message': False})
        return self._issue_ssl(domain)

    def _issue_ssl(self, domain):
        domain.write({'state': 'ssl_pending'})
        result = self.ssl.issue_ssl(domain)
        self.env['saas.domain.verification'].log(domain, 'ssl',
            'success' if result['success'] else 'error', details=result.get('error'))
        if result['success']:
            expires_at = None
            if result.get('expires_at'):
                try:
                    expires_at = fields.Datetime.from_string(result['expires_at'][:19].replace('T', ' '))
                except Exception:
                    pass
            domain.write({'state': 'active', 'ssl_issued': True, 'ssl_issued_at': fields.Datetime.now(),
                          'ssl_expires_at': expires_at, 'activated_at': fields.Datetime.now(),
                          'error_message': False})
            self.env['saas.event']._publish('domain.ssl.issued', model='saas.domain', record_id=domain.id,
                payload={'domain': domain.domain, 'tenant_id': domain.tenant_id.id}, tenant_id=domain.tenant_id.id)
            self.env['saas.event']._publish('domain.verified', model='saas.domain', record_id=domain.id,
                payload={'domain': domain.domain, 'tenant_id': domain.tenant_id.id}, tenant_id=domain.tenant_id.id)
            return self._notify(domain, 'success', _('Domain %s is now active with HTTPS!', domain.domain))
        domain.write({'state': 'failed', 'error_message': _('SSL issuance failed: %s', result.get('error', 'unknown'))})
        return self._notify(domain, 'danger', _('SSL issuance failed: %s', result.get('error', 'unknown')))

    def remove_domain(self, domain):
        if domain.state == 'active':
            self.ssl.remove_domain(domain)
        if domain.is_primary:
            domain.tenant_id.sudo().with_context(bypass_fsm=True).write({'custom_domain': False})
        domain.write({'state': 'removed', 'is_primary': False})

    def cron_verify_pending(self):
        pending = self.env['saas.domain'].search([
            ('state', 'in', ['pending_dns', 'dns_verified']), ('check_count', '<', 100)])
        for domain in pending:
            try:
                self.verify_domain(domain)
            except Exception as e:
                _logger.error('Cron verify failed for %s: %s', domain.domain, e)

    def cron_renew_ssl(self):
        from datetime import timedelta
        cutoff = fields.Datetime.now() + timedelta(days=30)
        expiring = self.env['saas.domain'].search([
            ('state', '=', 'active'), ('ssl_issued', '=', True), ('ssl_expires_at', '<=', cutoff)])
        for domain in expiring:
            try:
                result = self.ssl.renew_ssl(domain)
                if result.get('success') and result.get('expires_at'):
                    domain.write({'ssl_expires_at': fields.Datetime.from_string(
                        result['expires_at'][:19].replace('T', ' '))})
            except Exception as e:
                _logger.error('SSL renewal failed for %s: %s', domain.domain, e)

    def _notify(self, domain, type_, message):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': type_, 'message': message, 'sticky': type_ in ('warning', 'danger')}}
