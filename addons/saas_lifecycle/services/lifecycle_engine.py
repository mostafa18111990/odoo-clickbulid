from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class LifecycleEngine:
    def __init__(self, env):
        self.env = env

    def run(self):
        now = fields.Datetime.now()
        total_exec = total_skip = total_err = 0
        rules = self.env['saas.lifecycle.rule'].search([('active', '=', True)], order='sequence asc, id asc')
        for rule in rules:
            try:
                ex, sk = self._process_rule(rule, now)
                total_exec += ex
                total_skip += sk
                if ex > 0:
                    rule.write({'last_run': now, 'execution_count': rule.execution_count + ex})
            except Exception as e:
                total_err += 1
                _logger.error('LifecycleEngine: rule "%s" failed: %s', rule.name, e)
        _logger.info('LifecycleEngine: %d executed, %d skipped, %d errors', total_exec, total_skip, total_err)
        return {'executed': total_exec, 'skipped': total_skip, 'errors': total_err}

    def _process_rule(self, rule, now):
        tenants = self.env['saas.tenant'].search([('state', '=', rule.from_state)])
        executed = skipped = 0
        for tenant in tenants:
            try:
                if self._should_execute(rule, tenant, now):
                    self._execute_rule(rule, tenant, now)
                    executed += 1
                else:
                    skipped += 1
            except Exception as e:
                _logger.error('Rule "%s" failed for %s: %s', rule.name, tenant.subdomain, e)
                self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='lifecycle_rule',
                    result='failed', description=f'Rule "{rule.name}" failed: {e}', rule=rule, error=str(e))
        return executed, skipped

    # Rules that stop or destroy a tenant. For these we must NEVER guess the
    # reference timestamp — a missing trial_ends_at/suspended_at must mean
    # "skip", never "fall back to create_date and fire immediately". Falling
    # back to create_date here is what mass-deleted tenants whose date field
    # was momentarily blank.
    _DESTRUCTIVE_TARGETS = {'suspended', 'cancelled', 'archived', 'deleted'}

    def _should_execute(self, rule, tenant, now):
        if not rule.matches_tenant(tenant):
            return False
        ref = rule.get_tenant_entry_time(tenant)
        is_destructive = rule.action == 'transition' and rule.to_state in self._DESTRUCTIVE_TARGETS
        if ref is None:
            if is_destructive:
                # No trustworthy anchor date → refuse to stop/delete. Log it
                # so a misconfigured tenant is visible instead of purged.
                _logger.warning('Lifecycle: skipping destructive rule "%s" on %s '
                                '— no reference date (%s)', rule.name, tenant.subdomain,
                                rule.delay_type)
                return False
            # Non-destructive rules (reminders, win-back) may use a soft anchor.
            ref = tenant.saas_updated_at or tenant.create_date
        if not ref:
            return False
        if (now - ref).total_seconds() / 3600 < rule.delay_hours:
            return False
        already = self.env['saas.lifecycle.log'].search_count([
            ('tenant_id', '=', tenant.id), ('lifecycle_rule_id', '=', rule.id),
            ('result', '=', 'success'), ('create_date', '>=', ref)])
        return not already

    def _execute_rule(self, rule, tenant, now):
        old = tenant.state
        if rule.send_email and rule.email_template_id:
            try:
                rule.email_template_id.send_mail(tenant.id, force_send=True)
            except Exception as e:
                _logger.warning('Email send failed for "%s": %s', rule.name, e)
        if rule.action == 'transition':
            self._do_transition(rule, tenant, old)
        elif rule.action == 'send_email':
            self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='lifecycle_rule',
                result='success', description=f'Rule "{rule.name}": email sent', rule=rule)
        elif rule.action == 'publish_event':
            self.env['saas.event']._publish(event_type=rule.event_to_publish, model='saas.tenant',
                record_id=tenant.id, payload={'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
                'rule_name': rule.name, 'triggered_at': str(now)}, tenant_id=tenant.id)
            self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='lifecycle_rule',
                result='success', description=f'Rule "{rule.name}": event {rule.event_to_publish}', rule=rule)
        elif rule.action == 'winback':
            self._trigger_winback(rule, tenant)

    def _do_transition(self, rule, tenant, old):
        fn = {
            'pending_payment': tenant.action_pending_payment, 'active': tenant.action_activate,
            'grace_period': tenant.action_start_grace_period, 'suspended': tenant.action_suspend,
            'cancelled': lambda: tenant.action_cancel(cancelled_by='system'),
            'archived': tenant.action_archive_tenant, 'deleted': tenant.action_delete_tenant,
        }.get(rule.to_state)
        if not fn:
            raise ValueError(f'No transition handler for to_state={rule.to_state}')
        fn()
        self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='lifecycle_rule', result='success',
            description=f'Rule "{rule.name}": {old} -> {rule.to_state}', rule=rule,
            state_before=old, state_after=rule.to_state)

    def _trigger_winback(self, rule, tenant):
        if not tenant.winback_eligible:
            self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='winback', result='skipped',
                description='Win-back skipped: tenant opted out', rule=rule)
            return
        tenant.with_context(bypass_fsm=True).write({'winback_triggered_at': fields.Datetime.now()})
        self.env['saas.event']._publish(event_type='tenant.cancelled', model='saas.tenant',
            record_id=tenant.id, payload={'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
            'email': tenant.customer_email,
            'plan': tenant.plan_id.code if tenant.plan_id else '',
            'cancel_reason': tenant.cancellation_reason_id.code if tenant.cancellation_reason_id else ''},
            tenant_id=tenant.id)
        self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='winback', result='success',
            description=f'Win-back triggered via "{rule.name}"', rule=rule)
