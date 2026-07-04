from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _saas_max_users(self):
        """Plan user limit set by the ClickBuild provisioner. 0 = unlimited."""
        val = self.env['ir.config_parameter'].sudo().get_param('saas.max_users', '0')
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    def _saas_check_user_limit(self):
        limit = self._saas_max_users()
        if limit <= 0:
            return
        # Internal (non-portal, non-public) active users only.
        count = self.sudo().search_count([('share', '=', False), ('active', '=', True)])
        if count > limit:
            raise ValidationError(_(
                'وصلت إلى الحد الأقصى للمستخدمين في باقتك (%(limit)s مستخدم). '
                'قم بترقية باقتك من بوابة ClickBuild لإضافة مستخدمين إضافيين.\n\n'
                'You have reached your plan\'s user limit (%(limit)s users). '
                'Upgrade your plan from the ClickBuild portal to add more users.',
                limit=limit))

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if any(not u.share for u in users):
            self._saas_check_user_limit()
        return users

    def write(self, vals):
        res = super().write(vals)
        # Reactivating an archived user, or promoting portal -> internal via a
        # groups change, both consume a seat — re-check in those cases.
        if vals.get('active') or 'groups_id' in vals or 'group_ids' in vals:
            self._saas_check_user_limit()
        return res
