from odoo import http
from odoo.http import request


class TrailerInspectionPortal(http.Controller):
    def _branding(self, inspection=None):
        """Portal pages carry the operating company's identity.

        A verified report shows the company that issued it; elsewhere the
        visitor sees the company running the portal.
        """
        company = inspection.company_id if inspection else None
        return {"company": company or request.env.company}

    @http.route("/trailer-inspection/verify/<string:token>", type="http", auth="public", website=False, sitemap=False)
    def verify_report(self, token, **kwargs):
        inspection = request.env["trailer.inspection"].sudo().search(
            [("access_token", "=", token), ("state", "=", "approved")], limit=1
        )
        return request.render(
            "trailer_inspection_saso.portal_trailer_verification",
            {"inspection": inspection, "valid": bool(inspection),
             **self._branding(inspection)},
        )

    @http.route("/my/trailer-inspections", type="http", auth="user", website=False)
    def client_inspections(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        inspections = request.env["trailer.inspection"].sudo().search(
            [("partner_id.commercial_partner_id", "=", partner.id)],
            order="inspection_date desc, id desc",
        )
        return request.render(
            "trailer_inspection_saso.portal_trailer_inspection_list",
            {"inspections": inspections, **self._branding()},
        )

    @http.route("/my/trailer-inspections/<int:inspection_id>", type="http", auth="user", website=False)
    def client_inspection_detail(self, inspection_id, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        inspection = request.env["trailer.inspection"].sudo().search(
            [("id", "=", inspection_id), ("partner_id.commercial_partner_id", "=", partner.id)],
            limit=1,
        )
        if not inspection:
            return request.not_found()
        return request.render(
            "trailer_inspection_saso.portal_trailer_inspection_detail",
            {"inspection": inspection, **self._branding(inspection)},
        )
