from odoo import fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MarketplaceService:
    def __init__(self, env):
        self.env = env
        from odoo.addons.saas_marketplace.services.app_install_bridge import AppInstallBridge
        self.bridge = AppInstallBridge(env)

    def get_catalog(self, tenant, category_code=None, search=None):
        domain = [('active', '=', True)]
        if category_code:
            cat = self.env['saas.marketplace.category'].search([('code', '=', category_code)], limit=1)
            if cat:
                domain.append(('category_id', '=', cat.id))
        if search:
            domain.append(('name', 'ilike', search))
        apps = self.env['saas.marketplace.app'].search(domain, order='sequence, name')
        installed = self.env['saas.tenant.app'].search([
            ('tenant_id', '=', tenant.id), ('state', '=', 'installed')])
        installed_ids = installed.mapped('app_id').ids
        result = []
        for app in apps:
            eligible, reason = app.is_eligible_for_tenant(tenant)
            result.append({'id': app.id, 'name': app.name, 'code': app.code,
                'short_desc': app.short_description, 'icon': app.icon, 'category': app.category_id.name,
                'pricing_model': app.pricing_model, 'price': app.price,
                'price_label': app.price_label, 'is_featured': app.is_featured,
                'is_popular': app.is_popular, 'installed': app.id in installed_ids,
                'eligible': eligible, 'reason': reason, 'install_count': app.install_count})
        return result

    def install_app(self, tenant, app_id):
        app = self.env['saas.marketplace.app'].browse(app_id).exists()
        if not app:
            raise UserError(_('App not found.'))
        eligible, reason = app.is_eligible_for_tenant(tenant)
        if not eligible:
            raise UserError(reason or _('Not eligible.'))
        existing = self.env['saas.tenant.app'].search([
            ('tenant_id', '=', tenant.id), ('app_id', '=', app.id),
            ('state', 'in', ['installing', 'installed'])], limit=1)
        if existing:
            raise UserError(_('App "%s" is already installed.', app.name))
        addon = None
        if app.pricing_model != 'free':
            addon = self._create_addon(tenant, app)
        tenant_app = self.env['saas.tenant.app'].create({
            'tenant_id': tenant.id, 'app_id': app.id,
            'addon_id': addon.id if addon else False, 'state': 'draft'})
        return self._execute_install(tenant_app)

    def _create_addon(self, tenant, app):
        subscription = tenant.current_subscription_id
        if not subscription:
            raise UserError(_('No active subscription found.'))
        addon = self.env['saas.subscription.addon'].create({
            'subscription_id': subscription.id, 'app_id': app.id, 'price': app.price,
            'pricing_model': app.pricing_model if app.pricing_model != 'one_time' else 'monthly',
            'currency': subscription.currency, 'state': 'active'})
        if app.pricing_model in ('monthly', 'yearly'):
            self.env['saas.subscription.line'].create({
                'subscription_id': subscription.id, 'line_type': 'addon',
                'name': f'Add-on: {app.name}', 'quantity': 1,
                'unit_price': addon.get_monthly_amount(),
                'period_start': fields.Date.today(),
                'period_end': subscription.current_period_end or fields.Date.today(),
                'billed': False})
        return addon

    def _execute_install(self, tenant_app):
        tenant = tenant_app.tenant_id
        app = tenant_app.app_id
        tenant_app.write({'state': 'installing'})
        result = self.bridge.install_module(tenant, app.technical_module)
        if result.get('success'):
            tenant_app.mark_installed()
            self._publish_install_event(tenant_app, 'installed')
            return {'success': True, 'message': _('App "%s" installed.', app.name)}
        elif result.get('pending'):
            tenant_app.write({'external_job_id': result.get('job_id', '')})
            return {'success': True, 'pending': True,
                    'message': _('Installing "%s" - this may take a few minutes.', app.name)}
        else:
            tenant_app.mark_failed(result.get('error', 'Unknown error'))
            return {'success': False, 'error': result.get('error')}

    def _publish_install_event(self, tenant_app, status):
        self.env['saas.event']._publish(
            event_type='subscription.upgraded' if status == 'installed' else 'provisioning.failed',
            model='saas.tenant.app', record_id=tenant_app.id,
            payload={'tenant_id': tenant_app.tenant_id.id, 'app_name': tenant_app.app_id.name,
                     'status': status}, tenant_id=tenant_app.tenant_id.id)

    def uninstall_app(self, tenant_app):
        tenant = tenant_app.tenant_id
        app = tenant_app.app_id
        dependents = self.env['saas.marketplace.app'].search([('dependency_app_ids', 'in', app.id)])
        for dep_app in dependents:
            installed = self.env['saas.tenant.app'].search_count([
                ('tenant_id', '=', tenant.id), ('app_id', '=', dep_app.id), ('state', '=', 'installed')])
            if installed:
                raise UserError(_('Cannot uninstall "%s" - "%s" depends on it.', app.name, dep_app.name))
        tenant_app.write({'state': 'uninstalling'})
        result = self.bridge.uninstall_module(tenant, app.technical_module)
        if result.get('success'):
            tenant_app.mark_uninstalled()
            if tenant_app.addon_id:
                tenant_app.addon_id.action_cancel()
                self.env['saas.subscription.line'].search([
                    ('subscription_id', '=', tenant.current_subscription_id.id),
                    ('line_type', '=', 'addon'), ('name', '=', f'Add-on: {app.name}'),
                    ('billed', '=', False)]).unlink()
            return {'success': True, 'message': _('App uninstalled.')}
        tenant_app.mark_failed(result.get('error', 'Uninstall failed'))
        return {'success': False, 'error': result.get('error')}

    def cron_verify_installs(self):
        pending = self.env['saas.tenant.app'].search([
            ('state', '=', 'installing'), ('external_job_id', '!=', False)])
        _logger.info('Cron: %d app installs pending verification', len(pending))
