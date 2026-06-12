from odoo import fields
from datetime import datetime, timezone, timedelta


class TenantRepository:
    def __init__(self, env):
        self.env = env
        self._model = env['saas.tenant']

    def find_by_id(self, tenant_id):
        return self._model.browse(tenant_id).exists()

    def find_by_subdomain(self, subdomain):
        return self._model.search([('subdomain', '=', subdomain)], limit=1)

    def find_by_api_instance_id(self, api_id):
        return self._model.search([('api_instance_id', '=', api_id)], limit=1)

    def find_active(self):
        return self._model.search([('state', '=', 'active')])

    def find_trials(self):
        return self._model.search([('state', '=', 'trial')])

    def count_by_state(self):
        states = ['lead', 'trial', 'pending_payment', 'active', 'grace_period',
                  'suspended', 'cancelled', 'archived', 'deleted']
        return {s: self._model.search_count([('state', '=', s)]) for s in states}

    def count_new_this_month(self):
        from datetime import date
        today = date.today()
        month_start = fields.Datetime.from_string(f'{today.year}-{today.month:02d}-01 00:00:00')
        return self._model.search_count([('create_date', '>=', month_start)])

    def find_by_plan(self, plan_id):
        return self._model.search([('plan_id', '=', plan_id)])
