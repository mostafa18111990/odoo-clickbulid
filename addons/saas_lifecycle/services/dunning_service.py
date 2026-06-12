from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class DunningService:
    def __init__(self, env):
        self.env = env

    def run_dunning_cycle(self):
        now = fields.Datetime.now()
        processed = errors = 0
        for state in ('grace_period', 'suspended'):
            for tenant in self.env['saas.tenant'].search([('state', '=', state)]):
                try:
                    self._process_tenant(tenant, state, now)
                    processed += 1
                except Exception as e:
                    errors += 1
                    _logger.error('Dunning failed for %s: %s', tenant.subdomain, e)
        _logger.info('Dunning cycle: %d processed, %d errors', processed, errors)
        return {'processed': processed, 'errors': errors}

    def _process_tenant(self, tenant, state, now):
        rules = self._get_applicable_rules(tenant, state)
        if not rules:
            return
        executed = self.env['saas.dunning.attempt'].search([
            ('tenant_id', '=', tenant.id), ('state', 'in', ['executed', 'scheduled'])])
        done_numbers = set(executed.mapped('attempt_number'))
        next_rule = None
        for rule in rules:
            if rule.attempt_number not in done_numbers:
                next_rule = rule
                break
        if not next_rule:
            return
        ref = self._get_reference_time(tenant, state)
        if not ref:
            return
        if (now - ref).total_seconds() / 86400 < next_rule.delay_days:
            return
        self._execute_rule(tenant, next_rule, now)

    def _get_applicable_rules(self, tenant, state):
        rules = self.env['saas.dunning.rule'].search([
            ('active', '=', True), ('applies_to_state', '=', state)], order='attempt_number asc')
        return rules.filtered(lambda r: r.matches_tenant(tenant))

    def _get_reference_time(self, tenant, state):
        return {'grace_period': tenant.grace_started_at,
                'suspended': tenant.suspended_at}.get(state) or tenant.saas_updated_at

    def _execute_rule(self, tenant, rule, now):
        attempt = self.env['saas.dunning.attempt'].create({
            'tenant_id': tenant.id, 'rule_id': rule.id, 'attempt_number': rule.attempt_number,
            'scheduled_at': now, 'state': 'pending', 'payment_amount': tenant.last_payment_amount or 0})
        try:
            if rule.send_email and rule.email_template_id:
                rule.email_template_id.send_mail(tenant.id, force_send=True)
            if rule.action == 'retry_payment':
                self._retry_payment(tenant, attempt, rule)
            elif rule.action == 'send_email':
                attempt.mark_executed('email_sent')
            elif rule.action == 'suspend':
                old = tenant.state
                tenant.action_suspend()
                attempt.mark_executed('suspended')
                self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
                    result='success', description=f'Dunning "{rule.name}": suspended', attempt=attempt,
                    state_before=old, state_after='suspended')
            elif rule.action == 'cancel':
                old = tenant.state
                tenant.action_cancel(cancelled_by='system')
                attempt.mark_executed('cancelled')
                self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
                    result='success', description=f'Dunning "{rule.name}": cancelled', attempt=attempt,
                    state_before=old, state_after='cancelled')
        except Exception as e:
            attempt.mark_executed('error', error=str(e))
            self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
                result='failed', description=f'Dunning "{rule.name}" failed: {e}', attempt=attempt, error=str(e))
            raise

    def _retry_payment(self, tenant, attempt, rule):
        self.env['saas.event']._publish(
            event_type='payment.retry.scheduled', model='saas.tenant', record_id=tenant.id,
            payload={'tenant_id': tenant.id, 'subdomain': tenant.subdomain,
                     'amount': tenant.last_payment_amount or 0, 'attempt_number': rule.attempt_number,
                     'attempt_id': attempt.id, 'rule_name': rule.name}, tenant_id=tenant.id)
        attempt.write({'state': 'scheduled'})
        self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
            result='success', description=f'Payment retry scheduled (#{rule.attempt_number})', attempt=attempt)

    def on_payment_success(self, tenant, tx_id=None):
        for a in self.env['saas.dunning.attempt'].search([
                ('tenant_id', '=', tenant.id), ('state', 'in', ['scheduled', 'pending'])]):
            a.mark_executed('payment_success', tx_id=tx_id)
        if tenant.state in ('grace_period', 'suspended', 'pending_payment'):
            tenant.action_activate()
        self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
            result='success', description='Payment received - dunning ended, tenant activated')

    def on_payment_failure(self, tenant, error=None):
        for a in self.env['saas.dunning.attempt'].search([
                ('tenant_id', '=', tenant.id), ('state', 'in', ['scheduled', 'pending'])]):
            a.mark_executed('payment_failed', error=error)
        self.env['saas.lifecycle.log'].log(tenant=tenant, log_type='dunning_attempt',
            result='failed', description=f'Payment retry failed: {error or "unknown"}')
