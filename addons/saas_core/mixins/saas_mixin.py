from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SaasMixin(models.AbstractModel):
    _name = 'saas.mixin'
    _description = 'SaaS Base Mixin'

    saas_created_by = fields.Many2one('res.users', string='Created By', readonly=True, copy=False, index=True)
    saas_updated_by = fields.Many2one('res.users', string='Last Updated By', readonly=True, copy=False)
    saas_created_at = fields.Datetime(string='Created At', readonly=True, copy=False)
    saas_updated_at = fields.Datetime(string='Last Updated At', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault('saas_created_by', self.env.uid)
            vals.setdefault('saas_updated_by', self.env.uid)
            vals.setdefault('saas_created_at', now)
            vals.setdefault('saas_updated_at', now)
        records = super().create(vals_list)
        for record in records:
            self._publish_audit(record, 'create')
        return records

    def write(self, vals):
        vals['saas_updated_by'] = self.env.uid
        vals['saas_updated_at'] = fields.Datetime.now()
        result = super().write(vals)
        for record in self:
            self._publish_audit(record, 'write')
        return result

    def unlink(self):
        for record in self:
            self._publish_audit(record, 'unlink')
        return super().unlink()

    def _publish_event(self, event_type, payload=None):
        try:
            self.env['saas.event'].sudo()._publish(
                event_type=event_type, model=self._name,
                record_id=self.id if hasattr(self, 'id') else None,
                payload=payload or {},
            )
        except Exception as e:
            _logger.warning('SaasMixin._publish_event failed: %s', e)

    def _publish_audit(self, record, action):
        try:
            desc = getattr(record, 'name', None) or getattr(record, 'subdomain', None) or str(record.id)
            self.env['saas.audit.log'].sudo().log_action(
                model=self._name, record_id=record.id, action=action,
                description=f'{self._description}: {desc} - {action}', user_id=self.env.uid,
            )
        except Exception as e:
            _logger.warning('SaasMixin._publish_audit failed: %s', e)

    def _get_saas_config(self):
        return self.env['saas.config']._get_config()
