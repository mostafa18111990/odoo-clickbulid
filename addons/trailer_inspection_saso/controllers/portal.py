import re

from odoo import fields, http
from odoo.http import content_disposition, request

REPORT = "trailer_inspection_saso.action_report_trailer_inspection"


class TrailerInspectionPortal(http.Controller):
    def _customer_inspection(self, inspection_id):
        """The inspection, but only if it belongs to the caller."""
        partner = request.env.user.partner_id.commercial_partner_id
        return request.env["trailer.inspection"].sudo().search(
            [("id", "=", inspection_id),
             ("partner_id.commercial_partner_id", "=", partner.id)],
            limit=1,
        )

    def _pdf_response(self, inspection):
        """Stream the branded report as a download.

        Rendering runs as sudo because the caller is a portal user without
        read access to the inspection models; the record was resolved from
        their own partner (or an access token) before we get here.
        """
        pdf, _content_type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            REPORT, res_ids=inspection.ids
        )
        filename = "%s.pdf" % re.sub(r"[^\w.-]+", "-", inspection.name or "inspection")
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf)),
            ("Content-Disposition", content_disposition(filename)),
        ])

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
            [("access_token", "=", token), ("state", "in", ("approved", "revoked"))], limit=1
        )
        # A revoked report is named as such: "not found" would hide from a
        # checkpoint that the paper in front of them was withdrawn.
        revoked = inspection.state == "revoked"
        # A genuine report past its validity must not read as currently valid
        # to whoever scans the QR code at a checkpoint.
        expired = bool(
            inspection and not revoked and inspection.report_valid_until
            and inspection.report_valid_until < fields.Date.context_today(inspection)
        )
        return request.render(
            "trailer_inspection_saso.portal_trailer_verification",
            {"inspection": inspection, "valid": bool(inspection) and not revoked,
             "revoked": revoked, "expired": expired, **self._branding(inspection)},
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
        inspection = self._customer_inspection(inspection_id)
        if not inspection:
            return request.not_found()
        return request.render(
            "trailer_inspection_saso.portal_trailer_inspection_detail",
            {"inspection": inspection, **self._branding(inspection)},
        )

    @http.route("/my/trailer-inspections/<int:inspection_id>/report", type="http",
                auth="user", website=False, sitemap=False)
    def client_inspection_report(self, inspection_id, **kwargs):
        """The customer's own copy of the report.

        Only approved inspections are downloadable: an unapproved one has no
        standing and its checklist can still change.
        """
        inspection = self._customer_inspection(inspection_id)
        if not inspection or inspection.state != "approved":
            return request.not_found()
        return self._pdf_response(inspection)

    @http.route("/trailer-inspection/verify/<string:token>/report", type="http",
                auth="public", website=False, sitemap=False)
    def verify_report_pdf(self, token, **kwargs):
        """Report download for whoever scanned the verification QR."""
        inspection = request.env["trailer.inspection"].sudo().search(
            [("access_token", "=", token), ("state", "=", "approved")], limit=1
        )
        if not inspection:
            return request.not_found()
        return self._pdf_response(inspection)
