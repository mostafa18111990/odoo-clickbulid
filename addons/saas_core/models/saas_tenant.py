from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    'lead': ['trial', 'cancelled'],
    'trial': ['pending_payment', 'active', 'cancelled', 'suspended'],
    'pending_payment': ['active', 'trial', 'cancelled'],
    'active': ['grace_period', 'suspended', 'cancelled'],
    'grace_period': ['active', 'suspended', 'cancelled'],
    # 'deleted' allowed so the lifecycle engine can auto-purge suspended
    # tenants that never paid (final backup is kept by the destroyer).
    'suspended': ['active', 'cancelled', 'deleted'],
    'cancelled': ['archived'],
    'archived': ['deleted', 'active'],
    'deleted': [],
}


class SaasTenant(models.Model):
    _name = 'saas.tenant'
    _inherit = ['saas.tenant', 'saas.mixin']
    _description = 'SaaS Tenant (Extended)'

    state = fields.Selection(
        selection=[
            ('lead', 'Lead'), ('trial', 'Trial'), ('pending_payment', 'Pending Payment'),
            ('active', 'Active'), ('grace_period', 'Grace Period'), ('suspended', 'Suspended'),
            ('cancelled', 'Cancelled'), ('archived', 'Archived'), ('deleted', 'Deleted'),
        ],
        string='Status', default='lead', tracking=True, required=True, index=True)

    lead_source = fields.Selection(
        selection=[('website', 'Website'), ('google_ads', 'Google Ads'), ('referral', 'Referral'),
                   ('reseller', 'Reseller'), ('direct', 'Direct Sales'), ('api', 'API'), ('other', 'Other')],
        string='Lead Source', default='website')
    lead_date = fields.Datetime(string='Lead Date', readonly=True, default=fields.Datetime.now)
    referral_code = fields.Char(string='Referral Code', index=True)
    coupon_code = fields.Char(string='Coupon Code')
    # ISO country code chosen at signup (SA, AE, EG…). Drives which Odoo
    # localization (chart of accounts, taxes, e-invoicing) is auto-installed and
    # which country/currency the tenant's company is set to at provisioning.
    customer_country = fields.Char(string='Customer Country', default='SA', index=True)
    # Sector chosen at signup (homepage industry cards / signup form). Drives
    # which Odoo apps are auto-installed at provisioning — e.g. retail gets
    # POS + Inventory + Sales + Purchase + HR + Fleet on top of accounting.
    industry = fields.Selection(
        selection=[
            ('retail',          'Retail & Shops'),
            ('restaurant',      'Restaurants & Cafés'),
            ('ecommerce',       'E-Commerce'),
            ('trading',         'Import & Export'),
            ('construction',    'Construction'),
            ('manufacturing',   'Manufacturing'),
            ('services',        'Professional Services'),
            ('healthcare',      'Healthcare & Clinics'),
            ('education',       'Education & Training'),
            ('real_estate',     'Real Estate'),
            ('logistics',       'Logistics & Transport'),
            ('hospitality',     'Hotels & Tourism'),
            ('accounting',      'Accounting & Finance'),
            ('agriculture',     'Agriculture'),
            ('technology',      'Technology & Software'),
            ('other',           'Other'),
        ],
        string='Industry / Sector', index=True,
        help='Business sector chosen by the customer at signup.')

    trial_started_at = fields.Datetime(string='Trial Started', readonly=True)
    trial_ends_at = fields.Datetime(string='Trial Ends At', index=True)
    trial_reminder_sent = fields.Char(string='Trial Reminders Sent', default='')

    grace_started_at = fields.Datetime(string='Grace Period Started', readonly=True)
    grace_ends_at = fields.Datetime(string='Grace Period Ends', index=True)

    activated_at = fields.Datetime(string='Activated At', readonly=True)
    suspended_at = fields.Datetime(string='Suspended At', readonly=True)
    cancelled_at = fields.Datetime(string='Cancelled At', readonly=True)
    archived_at = fields.Datetime(string='Archived At', readonly=True)
    deleted_at = fields.Datetime(string='Deleted At', readonly=True)

    # Edition (related from plan, also persisted so we can route correctly even
    # if the plan is unlinked later). Set at provisioning time and frozen.
    edition = fields.Selection(
        selection=[('community', 'Community'), ('enterprise', 'Enterprise')],
        string='Odoo Edition', default='community', required=True, index=True,
        copy=False,
        help='Which Odoo binary serves this tenant. Set automatically from the '
             'chosen plan at signup; switched only by an explicit upgrade flow.')

    api_instance_id = fields.Char(string='FastAPI Instance ID', readonly=True, index=True)
    provisioning_job_ids = fields.One2many('saas.provisioning.job', 'tenant_id', string='Provisioning Jobs')
    provisioning_job_count = fields.Integer(string='Jobs', compute='_compute_job_count')

    billing_cycle = fields.Selection([('monthly', 'Monthly'), ('yearly', 'Yearly')],
                                     string='Billing Cycle', default='monthly')
    next_billing_date = fields.Date(string='Next Billing Date', index=True)
    payment_retry_count = fields.Integer(string='Payment Retry Count', default=0, readonly=True)
    last_payment_date = fields.Date(string='Last Payment Date', readonly=True)
    last_payment_amount = fields.Float(string='Last Payment Amount', digits=(10, 2), readonly=True)

    # Seats purchased by the customer (per-user pricing). 0 = fall back to
    # the plan's max_users. Editing this from the backend syncs the limit
    # into the tenant database within 2 minutes (host sweeper).
    user_count = fields.Integer(string='Purchased Users (Seats)', default=0)
    seat_monthly_cost = fields.Float(string='Monthly Cost (SAR)',
                                     compute='_compute_seat_monthly_cost', digits=(10, 2))

    @api.depends('user_count', 'plan_id', 'plan_id.pricing_mode',
                 'plan_id.price_per_user', 'plan_id.monthly_price')
    def _compute_seat_monthly_cost(self):
        for rec in self:
            rec.seat_monthly_cost = rec.plan_id.price_for_users(rec.user_count) if rec.plan_id else 0.0

    def effective_max_users(self):
        self.ensure_one()
        return self.user_count or (self.plan_id.max_users if self.plan_id else 0) or 0

    trial_days_left = fields.Integer(string='Trial Days Left', compute='_compute_trial_days_left')
    # When the platform will auto-purge a suspended tenant (suspended_at +
    # the "Suspended -> Delete" lifecycle rule delay). Display-only helper so
    # the admin sees exactly when the customer's data disappears.
    auto_delete_at = fields.Datetime(string='Auto-Delete On', compute='_compute_auto_delete_at')

    def _compute_auto_delete_at(self):
        rule = self.env['saas.lifecycle.rule'].sudo().search([
            ('from_state', '=', 'suspended'), ('to_state', '=', 'deleted'),
            ('action', '=', 'transition'), ('active', '=', True)], limit=1)
        for rec in self:
            if rec.state == 'suspended' and rec.suspended_at and rule:
                rec.auto_delete_at = rec.suspended_at + timedelta(hours=rule.delay_hours)
            else:
                rec.auto_delete_at = False

    @api.depends('provisioning_job_ids')
    def _compute_job_count(self):
        for rec in self:
            rec.provisioning_job_count = len(rec.provisioning_job_ids)

    @api.depends('trial_ends_at', 'state')
    def _compute_trial_days_left(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for rec in self:
            if rec.trial_ends_at and rec.state == 'trial':
                rec.trial_days_left = max(0, (rec.trial_ends_at - now).days)
            else:
                rec.trial_days_left = 0

    def _validate_transition(self, new_state):
        self.ensure_one()
        allowed = ALLOWED_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise UserError(_('Cannot transition %(n)s from %(f)s to %(t)s. Allowed: %(a)s',
                              n=self.name, f=self.state, t=new_state, a=', '.join(allowed) or 'none'))

    def _do_state_change(self, new_state, vals=None):
        self.ensure_one()
        self._validate_transition(new_state)
        old_state = self.state
        super(SaasTenant, self).write(dict(vals or {}, state=new_state))
        event_map = {
            'trial': 'tenant.trial.started', 'active': 'tenant.activated',
            'pending_payment': 'tenant.trial.expired', 'grace_period': 'tenant.grace_period.started',
            'suspended': 'tenant.suspended', 'cancelled': 'tenant.cancelled',
            'archived': 'tenant.archived', 'deleted': 'tenant.deleted',
        }
        if event_map.get(new_state):
            self._publish_event(event_map[new_state], {
                'tenant_id': self.id, 'subdomain': self.subdomain,
                'old_state': old_state, 'new_state': new_state})
        self.env['saas.audit.log'].log_action(
            model='saas.tenant', record_id=self.id, action='write',
            description=f'Tenant {self.subdomain}: {old_state} -> {new_state}',
            tenant_id=self.id, old_values={'state': old_state}, new_values={'state': new_state})

    def action_start_trial(self):
        config = self.env['saas.config']._get_config()
        now = fields.Datetime.now()
        self._do_state_change('trial', {'trial_started_at': now,
                                        'trial_ends_at': now + timedelta(days=config.trial_days)})

    def action_provision(self):
        self.ensure_one()
        config = self.env['saas.config']._get_config()
        if self.state == 'lead':
            self.action_start_trial()
        # Remote-hosted tenants (saas_external_server module) are provisioned
        # on the customer's own server over SSH, not on this platform.
        if getattr(self, 'external_server_id', False):
            from odoo.addons.saas_external_server.services.remote_provisioning import RemoteProvisioningService
            return RemoteProvisioningService(self.env).provision(self)
        if config.use_api_bridge:
            from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
            return ProvisioningBridgeService(self.env).provision(self)
        # LOCAL FALLBACK: queue a host-side provisioning request that will
        # create the Postgres DB (bare subdomain name, matching dbfilter=^%d$),
        # initialize Odoo, set the admin user, then drop a cert-request.
        # We DO NOT call super().action_provision() here — the base module
        # would create an empty `tenant_<sub>` DB that the dbfilter cannot
        # resolve. The host sweeper does it correctly.
        from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
        result = ProvisioningBridgeService(self.env)._queue_local_provision(self)
        # Return the one-time admin password to the caller so it can be shown
        # to the user on the signup success page (we don't have email sending
        # configured in this build).
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Workspace queued'),
                'message': _('Your workspace will be ready within 2 minutes.'),
                'type': 'success',
                'sticky': False,
            },
            'queued_subdomain': result.get('instance_id'),
            'admin_password_one_time': result.get('admin_password_one_time'),
        }

    def action_activate(self):
        now = fields.Datetime.now()
        was_suspended = self.state == 'suspended'
        self._do_state_change('active', {'activated_at': self.activated_at or now,
                                         'payment_retry_count': 0, 'last_payment_date': fields.Date.today()})
        if was_suspended:
            # Physically restore the tenant's nginx vhost (was blocked).
            self._queue_physical_flag('activate')
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'success', 'message': _('Tenant activated successfully.')}}

    def action_start_grace_period(self):
        config = self.env['saas.config']._get_config()
        now = fields.Datetime.now()
        self._do_state_change('grace_period', {
            'grace_started_at': now, 'grace_ends_at': now + timedelta(days=config.grace_period_days),
            'payment_retry_count': self.payment_retry_count + 1})

    def action_suspend(self):
        self._do_state_change('suspended', {'suspended_at': fields.Datetime.now()})
        # Physically block the tenant: nginx swaps the vhost for a bilingual
        # "subscription expired — renew to reactivate" page within 2 minutes.
        self._queue_physical_flag('suspend')
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'message': _('Tenant suspended.')}}

    def action_extend_trial(self):
        """Extend the tenant's lock date by 7 days (admin quick action).

        Works from any state: on a live trial it just pushes trial_ends_at;
        on a SUSPENDED tenant it also flips it back to trial and physically
        unblocks the nginx vhost, cancelling the auto-delete countdown.
        """
        now = fields.Datetime.now()
        for tenant in self:
            base = tenant.trial_ends_at if (tenant.trial_ends_at and tenant.trial_ends_at > now) else now
            new_end = base + timedelta(days=7)
            if tenant.state == 'suspended':
                tenant.with_context(bypass_fsm=True).write({
                    'state': 'trial', 'trial_ends_at': new_end, 'suspended_at': False})
                tenant._queue_physical_flag('activate')
                tenant._publish_event('tenant.trial.extended', {
                    'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
                    'new_trial_end': str(new_end), 'was_suspended': True})
            else:
                tenant.write({'trial_ends_at': new_end})
                tenant._publish_event('tenant.trial.extended', {
                    'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
                    'new_trial_end': str(new_end), 'was_suspended': False})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'success',
                           'message': _('Trial extended 7 days — new lock date: %s',
                                        self[:1].trial_ends_at)}}

    def _queue_physical_flag(self, kind):
        from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
        bridge = ProvisioningBridgeService(self.env)
        for tenant in self:
            try:
                svc = bridge
                if getattr(tenant, 'external_server_id', False):
                    from odoo.addons.saas_external_server.services.remote_provisioning import RemoteProvisioningService
                    svc = RemoteProvisioningService(self.env)
                if kind == 'suspend':
                    svc.suspend(tenant)
                else:
                    svc.activate(tenant)
            except Exception as e:
                _logger.error('Failed to queue %s for %s: %s', kind, tenant.subdomain, e)

    def action_cancel(self):
        self._do_state_change('cancelled', {'cancelled_at': fields.Datetime.now()})

    def action_archive_tenant(self):
        config = self.env['saas.config']._get_config()
        self._do_state_change('archived', {'archived_at': fields.Datetime.now()})
        self.write({'deleted_at': fields.Datetime.now() + timedelta(days=config.archived_retention_days)})

    def action_delete_tenant(self):
        self._do_state_change('deleted', {'deleted_at': fields.Datetime.now(), 'active': False})
        self._publish_event('tenant.deleted', {'tenant_id': self.id, 'subdomain': self.subdomain,
                                               'db_name': self.db_name})
        self._queue_physical_destruction()

    def _queue_physical_destruction(self):
        """Ask the host sweeper to permanently destroy the tenant database
        (final backup kept in /opt/backups/deleted, then dropdb + filestore +
        nginx vhost + SSL cert removal)."""
        from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
        bridge = ProvisioningBridgeService(self.env)
        for tenant in self:
            try:
                if getattr(tenant, 'external_server_id', False):
                    from odoo.addons.saas_external_server.services.remote_provisioning import RemoteProvisioningService
                    RemoteProvisioningService(self.env).delete(tenant)
                else:
                    bridge.delete(tenant)
            except Exception as e:
                _logger.error('Failed to queue destruction for %s: %s', tenant.subdomain, e)

    def action_destroy_permanently(self):
        """One-click hard delete from any state (admin only, confirmed in the
        UI). Marks the record deleted and queues physical destruction of the
        tenant database — it can never be started again."""
        for tenant in self:
            if tenant.state != 'deleted':
                tenant.with_context(bypass_fsm=True).write({
                    'state': 'deleted',
                    'deleted_at': fields.Datetime.now(),
                    'active': False,
                })
                tenant._publish_event('tenant.deleted', {
                    'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
                    'db_name': tenant.db_name, 'hard_delete': True})
        self._queue_physical_destruction()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False,
                           'message': _('Tenant destruction queued — the database '
                                        'will be permanently removed within 2 minutes.')}}

    def action_pending_payment(self):
        self._do_state_change('pending_payment', {})

    @api.model
    def cron_check_trials(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        reminder_days = self.env['saas.config'].get_trial_reminder_days()
        for tenant in self.search([('state', '=', 'trial')]):
            if not tenant.trial_ends_at:
                continue
            days_left = (tenant.trial_ends_at - now).days
            if days_left in reminder_days:
                ds = str(days_left)
                sent = (tenant.trial_reminder_sent or '').split(',')
                if ds not in sent:
                    tenant._publish_event('tenant.trial.reminder', {'tenant_id': tenant.id, 'days_left': days_left})
                    tenant.trial_reminder_sent = ','.join(filter(None, sent + [ds]))
        for tenant in self.search([('state', '=', 'trial'), ('trial_ends_at', '<', now)]):
            try:
                tenant.action_pending_payment()
            except Exception as e:
                _logger.error('Failed to expire trial for %s: %s', tenant.subdomain, e)

    @api.model
    def cron_check_grace_periods(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for tenant in self.search([('state', '=', 'grace_period'), ('grace_ends_at', '<', now)]):
            try:
                tenant.action_suspend()
                tenant._publish_event('tenant.grace_period.expired',
                                      {'tenant_id': tenant.id, 'subdomain': tenant.subdomain})
            except Exception as e:
                _logger.error('Grace expiry failed for %s: %s', tenant.subdomain, e)

    @api.model
    def cron_archive_cancelled(self):
        from datetime import datetime, timezone
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        for tenant in self.search([('state', '=', 'cancelled'), ('cancelled_at', '<', cutoff)]):
            try:
                tenant.action_archive_tenant()
            except Exception as e:
                _logger.error('Archive failed for %s: %s', tenant.subdomain, e)

    @api.model
    def cron_delete_archived(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for tenant in self.search([('state', '=', 'archived'), ('deleted_at', '<', now)]):
            try:
                tenant.action_delete_tenant()
            except Exception as e:
                _logger.error('Delete failed for %s: %s', tenant.subdomain, e)

    def write(self, vals):
        if 'state' in vals and not self.env.context.get('bypass_fsm'):
            for rec in self:
                new_state = vals['state']
                if rec.state != new_state:
                    if new_state not in ALLOWED_TRANSITIONS.get(rec.state, []):
                        raise UserError(_('Invalid state transition: %s -> %s', rec.state, new_state))
                    if rec.state == 'deleted':
                        raise UserError(_('Cannot modify a deleted tenant.'))
        res = super().write(vals)
        # Seat change from the backend → push the new limit into the live
        # tenant database (host sweeper applies it within 2 minutes).
        if 'user_count' in vals:
            for rec in self:
                if rec.api_instance_id and rec.state not in ('lead', 'deleted'):
                    rec._queue_seats_sync()
        return res

    def _queue_seats_sync(self):
        from odoo.addons.saas_core.services.provisioning_bridge import ProvisioningBridgeService
        bridge = ProvisioningBridgeService(self.env)
        for tenant in self:
            try:
                if getattr(tenant, 'external_server_id', False):
                    from odoo.addons.saas_external_server.services.remote_provisioning import RemoteProvisioningService
                    RemoteProvisioningService(self.env).sync_seats(tenant)
                else:
                    bridge.sync_seats(tenant)
            except Exception as e:
                _logger.error('Failed to queue seats sync for %s: %s', tenant.subdomain, e)
