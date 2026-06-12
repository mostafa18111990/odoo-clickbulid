from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaasTenantPortal(models.Model):
    _name = 'saas.tenant'
    _inherit = 'saas.tenant'

    portal_user_id = fields.Many2one('res.users', string='Portal User', ondelete='set null', copy=False)
    portal_access_granted = fields.Boolean(string='Portal Access Granted', default=False)

    def _create_portal_user(self):
        self.ensure_one()
        if self.portal_user_id:
            return self.portal_user_id
        if not self.customer_email:
            _logger.warning('Cannot create portal user: no email for %s', self.subdomain)
            return False
        existing = self.env['res.users'].sudo().search([('login', '=', self.customer_email)], limit=1)
        portal_group = self.env.ref('base.group_portal')
        if existing:
            user = existing
            user.sudo().write({'saas_tenant_id': self.id})
        else:
            user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
                'name': self.customer_name or self.name, 'login': self.customer_email,
                'email': self.customer_email, 'saas_tenant_id': self.id,
                'groups_id': [(6, 0, [portal_group.id])], 'company_id': self.env.company.id})
        self.write({'portal_user_id': user.id, 'portal_access_granted': True})
        try:
            user.sudo().action_reset_password()
        except Exception as e:
            _logger.warning('Could not send portal invite for %s: %s', self.subdomain, e)
        return user

    def action_grant_portal_access(self):
        for tenant in self:
            tenant._create_portal_user()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'success', 'message': _('Portal access granted and invitation sent.')}}

    def get_sso_url(self):
        self.ensure_one()
        return self.tenant_url or f'https://{self.subdomain}.clickbuild.com'
