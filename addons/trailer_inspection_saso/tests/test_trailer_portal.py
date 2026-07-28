from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from ..models.trailer_vin import calculate_vin_check_digit


def _vin(base17):
    """A VIN whose 9th-position check digit is valid for GSO 1780."""
    return base17[:8] + calculate_vin_check_digit(base17) + base17[9:]


class TrailerCase(TransactionCase):
    """Shared fixtures: an approved inspection plus one for someone else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inspector = cls.env["res.users"].create({
            "name": "Portal Test Inspector",
            "login": "trailer.portal.inspector",
            "group_ids": [Command.link(
                cls.env.ref("trailer_inspection_saso.group_trailer_manager").id)],
        })
        cls.customer = cls.env["res.partner"].create({
            "name": "Portal Customer", "is_company": True})
        cls.other_customer = cls.env["res.partner"].create({
            "name": "Other Customer", "is_company": True})

    @classmethod
    def _make_inspection(cls, partner, vin, approved=False):
        inspection = cls.env["trailer.inspection"].create({
            "partner_id": partner.id,
            "inspection_location": "Test Centre",
            "inspector_id": cls.inspector.id,
            "product_description": "O4 semi-trailer",
            "trailer_type": "semi_trailer",
            "category": "o4",
            "vin": vin,
            "manufacturer_name": "Test Manufacturer",
            "impartiality_confirmed": True,
        })
        if approved:
            # Approval is guarded by the workflow; the portal only cares about
            # the resulting state, so set it directly.
            inspection.write({
                "state": "approved",
                "report_valid_until": fields.Date.today() + timedelta(days=180),
            })
        return inspection


@tagged("post_install", "-at_install")
class TestPortalReportDownload(HttpCase, TrailerCase):
    """A customer may download their own approved report — and nothing else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal User",
            "login": "trailer.portal.user",
            "password": "trailer.portal.user",
            "partner_id": cls.env["res.partner"].create({
                "name": "Portal Contact", "parent_id": cls.customer.id}).id,
            "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
        })
        cls.mine_approved = cls._make_inspection(
            cls.customer, _vin("1FUJGLDR0CLBP8834"), approved=True)
        cls.mine_draft = cls._make_inspection(
            cls.customer, _vin("2HSCNAPR04C098211"))
        cls.theirs_approved = cls._make_inspection(
            cls.other_customer, _vin("3AKJGLDR0ESFR1290"), approved=True)
        cls.env.cr.flush()

    # Odoo swaps PDF rendering for HTML while tests run
    # (ir_actions_report: `current_test or test_enable` short-circuits), so
    # these assert the download is served and named, not its binary format.

    def test_customer_downloads_own_approved_report(self):
        self.authenticate("trailer.portal.user", "trailer.portal.user")
        response = self.url_open(
            "/my/trailer-inspections/%s/report" % self.mine_approved.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertIn(
            self.mine_approved.name.replace("/", "-"),
            response.headers.get("Content-Disposition", ""),
        )

    def test_customer_cannot_download_another_customers_report(self):
        self.authenticate("trailer.portal.user", "trailer.portal.user")
        response = self.url_open(
            "/my/trailer-inspections/%s/report" % self.theirs_approved.id)
        self.assertEqual(response.status_code, 404)

    def test_unapproved_report_is_not_downloadable(self):
        self.authenticate("trailer.portal.user", "trailer.portal.user")
        response = self.url_open(
            "/my/trailer-inspections/%s/report" % self.mine_draft.id)
        self.assertEqual(response.status_code, 404)

    def test_verification_token_serves_the_report(self):
        self.assertEqual(self.mine_approved.state, "approved")
        self.assertTrue(self.mine_approved.access_token)
        self.assertTrue(
            self.env["trailer.inspection"].sudo().search([
                ("access_token", "=", self.mine_approved.access_token),
                ("state", "=", "approved"),
            ]),
            "the controller's own lookup finds nothing",
        )
        response = self.url_open(
            "/trailer-inspection/verify/%s/report" % self.mine_approved.access_token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))

    def test_wrong_token_is_refused(self):
        response = self.url_open("/trailer-inspection/verify/not-a-token/report")
        self.assertEqual(response.status_code, 404)


class TestWorkspaceOverview(TrailerCase):
    """The landing screen's figures follow the records."""

    def test_counts_follow_inspection_states(self):
        before = self.env["trailer.inspection"].get_home_overview()["kpi"]
        draft = self._make_inspection(self.customer, _vin("4V4NC9GH0DN567123"))
        approved = self._make_inspection(
            self.customer, _vin("5TFUW5F10AX112233"), approved=True)
        after = self.env["trailer.inspection"].get_home_overview()["kpi"]
        self.assertEqual(after["open_count"], before["open_count"] + 1)
        self.assertEqual(after["approved_count"], before["approved_count"] + 1)
        self.assertTrue(draft.exists() and approved.exists())

    def test_overview_carries_the_company_identity(self):
        overview = self.env["trailer.inspection"].get_home_overview()
        self.assertEqual(overview["company"]["name"], self.env.company.name)
        self.assertEqual(overview["company"]["id"], self.env.company.id)


class TestChecklistBulkEntry(TrailerCase):
    """Clearing the uneventful majority of a 55-item checklist."""

    def setUp(self):
        super().setUp()
        self.inspection = self._make_inspection(
            self.customer, _vin("1FUJGLDR0CLBP8834"))
        self.inspection.write({"state": "in_progress"})

    def test_bulk_pass_only_touches_undecided_lines(self):
        lines = self.inspection.line_ids
        self.assertTrue(len(lines) > 1, "the checklist should be generated")
        judged = lines[0]
        judged.write({"result": "na"})
        pending_before = len(lines.filtered(lambda l: l.result == "pending"))

        touched = self.inspection.action_checklist_remaining_compliant()

        self.assertEqual(touched, pending_before)
        self.assertEqual(judged.result, "na", "an existing verdict was overwritten")
        self.assertFalse(lines.filtered(lambda l: l.result == "pending"))

    def test_bulk_not_applicable(self):
        self.inspection.action_checklist_remaining_not_applicable()
        self.assertFalse(
            self.inspection.line_ids.filtered(lambda l: l.result == "pending"))
        self.assertTrue(
            all(l.result == "na" for l in self.inspection.line_ids))

    def test_measured_lines_keep_their_derived_verdict(self):
        numeric = self.inspection.line_ids.filtered(
            lambda l: l.response_type == "numeric" and l.maximum_value)[:1]
        if not numeric:
            self.skipTest("no numeric requirement in the standard data")
        numeric.write({"measured_value": numeric.maximum_value + 1})
        numeric._evaluate_measurements()
        self.assertEqual(numeric.result, "no")
        self.assertTrue(numeric.observation, "the breach should be documented")

        self.inspection.action_checklist_remaining_compliant()

        self.assertEqual(numeric.result, "no",
                         "a measured failure was cleared by the bulk action")

    def test_bulk_entry_is_refused_outside_the_inspection(self):
        self.inspection.write({"state": "draft"})
        with self.assertRaises(UserError):
            self.inspection.action_checklist_remaining_compliant()

    def test_bulk_entry_reports_when_nothing_is_left(self):
        self.inspection.action_checklist_remaining_compliant()
        with self.assertRaises(UserError):
            self.inspection.action_checklist_remaining_compliant()


class TestAppBranding(TrailerCase):
    """The app tile carries the operator's company name."""

    def test_renaming_the_company_renames_the_app(self):
        menu = self.env.ref("trailer_inspection_saso.menu_trailer_root")
        self.env.company.write({"name": "Gulf Inspection Centre"})
        self.assertEqual(menu.name, "Gulf Inspection Centre")

    def test_name_is_written_for_every_installed_language(self):
        menu = self.env.ref("trailer_inspection_saso.menu_trailer_root")
        self.env.company.write({"name": "Desert Trailer Authority"})
        for code, _label in self.env["res.lang"].get_installed():
            self.assertEqual(
                menu.with_context(lang=code).name,
                "Desert Trailer Authority",
                "app tile fell back to the module name in %s" % code,
            )
