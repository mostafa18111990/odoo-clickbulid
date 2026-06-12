import logging

_logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, env):
        self.env = env

    def _get_request_context(self):
        ctx = {}
        try:
            from odoo.http import request as http_req
            if http_req and http_req.httprequest:
                ctx['ip_address'] = (http_req.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                                     or http_req.httprequest.remote_addr)
                ctx['user_agent'] = http_req.httprequest.user_agent.string[:200]
        except Exception:
            pass
        return ctx

    def log(self, model, action, description, record_id=None, tenant_id=None,
            old_values=None, new_values=None, severity='info'):
        ctx = self._get_request_context()
        return self.env['saas.audit.log'].log_action(
            model=model, action=action, description=description, record_id=record_id,
            tenant_id=tenant_id, old_values=old_values, new_values=new_values,
            severity=severity, ip_address=ctx.get('ip_address'), user_id=self.env.uid)

    def log_tenant_transition(self, tenant, old_state, new_state):
        return self.log(model='saas.tenant', action='write',
                        description=f'Tenant {tenant.subdomain}: {old_state} -> {new_state}',
                        record_id=tenant.id, tenant_id=tenant.id,
                        old_values={'state': old_state}, new_values={'state': new_state})

    def log_payment(self, tenant, amount, status, gateway):
        return self.log(model='saas.tenant', action='payment',
                        description=f'Payment {status}: {amount} SAR via {gateway} for {tenant.subdomain}',
                        record_id=tenant.id, tenant_id=tenant.id,
                        new_values={'amount': amount, 'status': status, 'gateway': gateway})
