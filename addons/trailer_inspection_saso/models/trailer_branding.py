"""White-label branding: the app carries the operator's own company name.

Each subscriber sees their company on the app tile and in the workspace
header, so the module reads as their inspection system rather than a
generic Odoo app.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

ROOT_MENU = "trailer_inspection_saso.menu_trailer_root"


class ResCompany(models.Model):
    _inherit = "res.company"

    def write(self, vals):
        result = super().write(vals)
        if vals.get("name"):
            self.env["trailer.inspection.branding"]._sync_app_name()
        return result


class TrailerBranding(models.AbstractModel):
    _name = "trailer.inspection.branding"
    _description = "Trailer Inspection App Branding"

    def _register_hook(self):
        """Re-assert the company name on the app tile after every load.

        Loading the module's translations rewrites the menu label, so a
        one-shot install hook is not enough to keep the operator's name on
        the tile through upgrades.
        """
        super()._register_hook()
        try:
            self._sync_app_name()
        except Exception:  # never block a registry load over a label
            _logger.warning("Trailer branding: app name sync skipped", exc_info=True)

    @api.model
    def _sync_app_name(self):
        """Name the app after the operator's company.

        The name is written for every installed language: the menu label is a
        translatable field, so a per-language term would otherwise put the
        generic module name back in front of some users.

        Multi-company databases keep the neutral name — no single company
        owns the tile there.
        """
        menu = self.env.ref(ROOT_MENU, raise_if_not_found=False)
        if not menu:
            return
        companies = self.env["res.company"].sudo().search([])
        if len(companies) != 1:
            return
        name = (companies.name or "").strip()
        if not name:
            return
        langs = self.env["res.lang"].sudo().get_installed() or [("en_US", "English")]
        for code, _label in langs:
            menu_in_lang = menu.sudo().with_context(lang=code)
            if menu_in_lang.name != name:
                menu_in_lang.write({"name": name})


def post_init_branding(env):
    env["trailer.inspection.branding"]._sync_app_name()
