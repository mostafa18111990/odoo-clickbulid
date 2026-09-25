import base64
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from ..models.trailer_vin import calculate_vin_check_digit


def _vin(base17):
    return base17[:8] + calculate_vin_check_digit(base17) + base17[9:]


EVIDENCE = base64.b64encode(b"evidence")


class IntegrityCase(TransactionCase):
    """Each role as it exists in a centre, and a report taken to approval
    through the real workflow rather than by setting its state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref("base.group_user")

        def user(login, group):
            return cls.env["res.users"].create({
                "name": login, "login": login,
                "group_ids": [Command.link(internal.id),
                              Command.link(cls.env.ref("trailer_inspection_saso.%s" % group).id)],
            })

        cls.clerk = user("trailer.integrity.clerk", "group_trailer_inspection_user")
        cls.inspector = user("trailer.integrity.inspector", "group_trailer_inspector")
        cls.other_inspector = user("trailer.integrity.other", "group_trailer_inspector")
        cls.reviewer = user("trailer.integrity.reviewer", "group_trailer_reviewer")
        cls.manager = user("trailer.integrity.manager", "group_trailer_manager")
        for inspector, number in ((cls.inspector, "AUTH-I-1"), (cls.other_inspector, "AUTH-I-2")):
            cls.env["trailer.inspector.authorization"].create({
                "user_id": inspector.id, "authorization_number": number,
                "valid_from": fields.Date.today() - timedelta(days=30),
                "valid_to": fields.Date.today() + timedelta(days=365),
            })
        cls.customer = cls.env["res.partner"].create({"name": "Integrity Customer", "is_company": True})
        cls.equipment = cls.env["trailer.inspection.equipment"].create({
            "name": "Calibrated tape", "code": "INT-TAPE", "serial_number": "INT-1",
            "calibration_due_date": fields.Date.today() + timedelta(days=200),
        })
        cls.vin = _vin("1M8GDM9A0KP042788")

    def _draft(self, vin=None, **values):
        vals = {
            "partner_id": self.customer.id, "inspection_location": "Yard",
            "inspector_id": self.inspector.id, "reviewer_id": self.reviewer.id,
            "product_description": "O3 semi-trailer", "trailer_type": "semi_trailer",
            "category": "o3", "vin": vin or self.vin, "manufacturer_name": "Test",
            "impartiality_confirmed": True,
        }
        vals.update(values)
        return self.env["trailer.inspection"].create(vals)

    def _complete_checklist(self, inspection):
        for line in inspection.line_ids:
            vals = {"result": "yes"}
            if line.response_type == "numeric":
                vals = {"measured_value": line.minimum_value or line.maximum_value or 1.0}
            if line.evidence_required:
                vals.update(evidence_attachment=EVIDENCE, evidence_filename="e.pdf")
            if line.equipment_required:
                vals["equipment_id"] = self.equipment.id
            line.write(vals)
        inspection.line_ids._evaluate_measurements()
        inspection.line_ids.filtered(lambda line: line.result == "no").write({"result": "yes"})

    def _submitted(self, vin=None):
        inspection = self._draft(vin)
        inspection.with_user(self.inspector).action_start()
        self._complete_checklist(inspection)
        inspection.write({"inspector_signature": EVIDENCE, "reviewer_signature": EVIDENCE})
        inspection.with_user(self.inspector).action_sign_inspector()
        inspection.with_user(self.inspector).action_submit()
        return inspection

    def _approved(self, vin=None):
        inspection = self._submitted(vin)
        inspection.with_user(self.reviewer).action_sign_reviewer()
        inspection.with_user(self.reviewer).action_approve()
        self.assertEqual(inspection.state, "approved")
        return inspection


class TestApprovedReportIsFinal(IntegrityCase):
    """An approved report cannot be reopened, altered or withdrawn by hand."""

    def test_start_cannot_reopen_an_approved_report(self):
        inspection = self._approved()
        with self.assertRaises(UserError):
            inspection.with_user(self.inspector).action_start()
        self.assertEqual(inspection.state, "approved")

    def test_reviewer_cannot_return_or_reject_an_approved_report(self):
        inspection = self._approved()
        with self.assertRaises(UserError):
            inspection.with_user(self.reviewer).action_return_to_inspector()
        with self.assertRaises(UserError):
            inspection.with_user(self.reviewer).action_reject()
        self.assertEqual(inspection.state, "approved")

    def test_approved_report_cannot_be_cancelled(self):
        inspection = self._approved()
        with self.assertRaises(AccessError):
            inspection.with_user(self.clerk).action_cancel()
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).action_cancel()

    def test_validity_and_notes_are_locked_too(self):
        inspection = self._approved()
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).write(
                {"report_valid_until": fields.Date.today() + timedelta(days=3650)})

    def test_checklist_lines_are_locked(self):
        inspection = self._approved()
        line = inspection.line_ids[:1]
        with self.assertRaises(UserError):
            line.with_user(self.inspector).write({"result": "no", "observation": "tampered"})
        with self.assertRaises(UserError):
            line.with_user(self.manager).unlink()
        with self.assertRaises(UserError):
            self.env["trailer.inspection.photo"].with_user(self.inspector).create({
                "inspection_id": inspection.id, "name": "late", "photo_type": "other",
                "photo": EVIDENCE})
        self.assertEqual(inspection.overall_result, "compliant")

    def test_closing_a_nonconformity_still_marks_its_line(self):
        inspection = self._approved()
        line = inspection.line_ids[:1]
        line.write({"nc_closed": True})
        self.assertTrue(line.nc_closed)


class TestWorkflowFieldsAreNotWritable(IntegrityCase):
    """State and signatures move only through the workflow actions."""

    def test_clerk_cannot_forge_an_approval(self):
        inspection = self._draft()
        with self.assertRaises(AccessError):
            inspection.with_user(self.clerk).write({
                "state": "approved", "reviewer_signed_by": self.reviewer.id,
                "reviewer_signed_on": fields.Datetime.now()})
        self.assertEqual(inspection.state, "draft")

    def test_clerk_cannot_create_an_approved_inspection(self):
        with self.assertRaises(AccessError):
            self.env["trailer.inspection"].with_user(self.clerk).create({
                "partner_id": self.customer.id, "inspection_location": "Yard",
                "inspector_id": self.inspector.id, "product_description": "x",
                "manufacturer_name": "x", "state": "approved"})

    def test_a_draft_created_from_the_form_is_accepted(self):
        inspection = self.env["trailer.inspection"].with_user(self.clerk).create({
            "partner_id": self.customer.id, "inspection_location": "Yard",
            "inspector_id": self.inspector.id, "product_description": "x",
            "manufacturer_name": "x", "state": "draft", "access_token": "form-default-token"})
        self.assertEqual(inspection.state, "draft")

    def test_clerk_cannot_cancel_or_reset(self):
        inspection = self._draft()
        with self.assertRaises(AccessError):
            inspection.with_user(self.clerk).action_cancel()
        inspection.with_user(self.manager).action_cancel()
        with self.assertRaises(AccessError):
            inspection.with_user(self.clerk).action_reset_draft()
        inspection.with_user(self.manager).action_reset_draft()
        self.assertEqual(inspection.state, "draft")

    def test_actions_refuse_the_wrong_state(self):
        inspection = self._draft()
        with self.assertRaises(UserError):
            inspection.with_user(self.inspector).action_submit()
        with self.assertRaises(UserError):
            inspection.with_user(self.reviewer).action_return_to_inspector()
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).action_create_reinspection()


class TestReturnWithdrawsSignatures(IntegrityCase):

    def test_returned_report_must_be_signed_again(self):
        inspection = self._submitted()
        inspection.with_user(self.reviewer).action_sign_reviewer()
        inspection.with_user(self.reviewer).action_return_to_inspector()
        self.assertEqual(inspection.state, "in_progress")
        self.assertFalse(inspection.inspector_signed_on)
        self.assertFalse(inspection.reviewer_signed_on)
        with self.assertRaises(UserError) as caught:
            inspection.with_user(self.inspector).action_submit()
        self.assertIn("signed", str(caught.exception))
        # and the data may change again while it is back with the inspector
        inspection.line_ids[:1].write({"observation": "re-examined"})


class TestInspectorAuthorization(IntegrityCase):

    def test_someone_elses_authorization_is_refused(self):
        other = self.env["trailer.inspector.authorization"].search(
            [("user_id", "=", self.other_inspector.id)])
        inspection = self._draft(authorization_id=other.id)
        with self.assertRaises(UserError):
            inspection.with_user(self.inspector).action_start()


class TestSameTrailerInspectedAgain(IntegrityCase):
    """A VIN recurs across inspections, but never on two open ones."""

    def test_periodic_inspection_after_approval(self):
        first = self._approved()
        second = self._draft(inspection_type="periodic")
        self.assertEqual(second.vin, first.vin)
        second.with_user(self.inspector).action_start()
        self.assertEqual(second.state, "in_progress")

    def test_two_open_inspections_of_one_trailer_are_refused(self):
        self._draft()
        with self.assertRaises(ValidationError):
            self._draft()

    def test_reinspection_keeps_the_trailer_identity_and_can_start(self):
        inspection = self._submitted()
        inspection.with_user(self.reviewer).write({"review_notes": "brake defect"})
        inspection.with_user(self.reviewer).action_return_to_inspector()
        line = inspection.line_ids.filtered(
            lambda item: item.response_type == "choice" and item.criticality != "critical")[:1]
        line.write({"result": "no", "observation": "defect"})
        inspection.with_user(self.inspector).action_sign_inspector()
        inspection.with_user(self.inspector).action_submit()
        inspection.with_user(self.reviewer).action_reject()
        action = inspection.with_user(self.inspector).action_create_reinspection()
        reinspection = self.env["trailer.inspection"].browse(action["res_id"])
        self.assertEqual(reinspection.vin, inspection.vin)
        reinspection.with_user(self.inspector).action_start()
        self.assertEqual(reinspection.state, "in_progress")

    def test_reopening_a_cancelled_one_respects_the_open_inspection(self):
        cancelled = self._draft()
        cancelled.with_user(self.manager).action_cancel()
        self._draft()
        with self.assertRaises(ValidationError):
            cancelled.with_user(self.manager).action_reset_draft()


class TestCalibrationFollowsTheCalendar(IntegrityCase):
    """Time passes without any write to the equipment record."""

    def _age(self, equipment, days_past_due):
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE trailer_inspection_equipment SET calibration_due_date = %s WHERE id = %s",
            [fields.Date.today() - timedelta(days=days_past_due), equipment.id])
        equipment.invalidate_recordset()

    def test_lapsed_equipment_is_refused_even_before_the_refresh(self):
        equipment = self.env["trailer.inspection.equipment"].create({
            "name": "Scale", "code": "INT-SCALE", "serial_number": "S-1",
            "calibration_due_date": fields.Date.today() + timedelta(days=60)})
        self._age(equipment, 10)
        self.assertEqual(equipment.calibration_status, "valid", "precondition: status is stale")
        inspection = self._draft()
        inspection.with_user(self.inspector).action_start()
        line = inspection.line_ids.filtered("equipment_required")[:1]
        if not line:
            self.skipTest("the standard data asks for no equipment")
        with self.assertRaises(ValidationError):
            line.write({"equipment_id": equipment.id})

    def test_daily_refresh_brings_the_status_up_to_date(self):
        equipment = self.env["trailer.inspection.equipment"].create({
            "name": "Brake meter", "code": "INT-BRK", "serial_number": "B-1",
            "calibration_due_date": fields.Date.today() + timedelta(days=60)})
        self._age(equipment, 1)
        self.env["trailer.inspection.equipment"]._cron_deadline_alerts()
        equipment.invalidate_recordset()
        self.assertEqual(equipment.calibration_status, "expired")


class TestUncalibratedEquipmentException(IntegrityCase):
    """Only a manager may let a lapsed instrument stay in use, with a reason
    and until a date; nobody else can grant or forge that permission."""

    def setUp(self):
        super().setUp()
        self.lapsed = self.env["trailer.inspection.equipment"].create({
            "name": "Lapsed scale", "code": "INT-LAPSED", "serial_number": "L-1",
            "calibration_due_date": fields.Date.today() - timedelta(days=5)})
        self.inspection = self._draft()
        self.inspection.with_user(self.inspector).action_start()
        self.line = self.inspection.line_ids.filtered("equipment_required")[:1]
        if not self.line:
            self.skipTest("the standard data asks for no equipment")

    def _allow(self, user, days=10, reason="Replacement scale arrives next week"):
        self.lapsed.with_user(user).write({
            "expired_use_allowed_until": fields.Date.today() + timedelta(days=days),
            "expired_use_reason": reason})

    def test_without_an_exception_the_instrument_is_refused(self):
        self.assertFalse(self.lapsed.usable_for_inspection)
        with self.assertRaises(ValidationError):
            self.line.write({"equipment_id": self.lapsed.id})

    def test_manager_exception_lets_it_be_used_and_is_recorded(self):
        self._allow(self.manager)
        self.assertEqual(self.lapsed.expired_use_approved_by, self.manager)
        self.assertTrue(self.lapsed.expired_use_approved_on)
        self.assertTrue(self.lapsed.usable_for_inspection)
        self.assertIn(self.lapsed, self.env["trailer.inspection.equipment"].search(
            [("usable_for_inspection", "=", True)]))
        self.line.with_user(self.inspector).write({"equipment_id": self.lapsed.id})
        self.assertEqual(self.line.equipment_id, self.lapsed)

    def test_only_a_manager_can_grant_it(self):
        for user in (self.inspector, self.reviewer, self.clerk):
            with self.assertRaises(AccessError):
                self._allow(user)
        self.assertFalse(self.lapsed.expired_use_allowed_until)

    def test_the_approver_cannot_be_forged(self):
        with self.assertRaises(AccessError):
            self.lapsed.with_user(self.manager).write({"expired_use_approved_by": self.reviewer.id})

    def test_a_reason_is_mandatory(self):
        with self.assertRaises(ValidationError):
            self._allow(self.manager, reason="  ")

    def test_the_exception_ends_on_its_date(self):
        self._allow(self.manager, days=-1)
        self.assertFalse(self.lapsed.usable_for_inspection)
        with self.assertRaises(ValidationError):
            self.line.write({"equipment_id": self.lapsed.id})

    def test_withdrawing_the_exception_clears_the_approval(self):
        self._allow(self.manager)
        self.lapsed.with_user(self.manager).write(
            {"expired_use_allowed_until": False, "expired_use_reason": False})
        self.assertFalse(self.lapsed.expired_use_approved_by)
        self.assertFalse(self.lapsed.usable_for_inspection)


class TestRevokeApproval(IntegrityCase):
    """A manager withdraws an approved report; it stays as signed."""

    def test_manager_revokes_with_a_reason(self):
        inspection = self._approved()
        action = inspection.with_user(self.manager).action_open_revoke_wizard()
        wizard = self.env[action["res_model"]].with_user(self.manager).with_context(
            action["context"]).create({"reason": "Wrong axle data on the certificate"})
        wizard.action_confirm()
        self.assertEqual(inspection.state, "revoked")
        self.assertEqual(inspection.revoked_by, self.manager)
        self.assertTrue(inspection.revoked_on)
        self.assertEqual(inspection.revocation_reason, "Wrong axle data on the certificate")
        self.assertTrue(inspection.inspector_signed_on, "the signed record is kept, not reopened")

    def test_only_a_manager_can_revoke(self):
        inspection = self._approved()
        for user in (self.reviewer, self.inspector, self.clerk):
            with self.assertRaises(AccessError):
                inspection.with_user(user).action_revoke("no")
            with self.assertRaises(AccessError):
                inspection.with_user(user).action_open_revoke_wizard()
        self.assertEqual(inspection.state, "approved")

    def test_a_reason_is_mandatory(self):
        inspection = self._approved()
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).action_revoke("   ")

    def test_only_an_approved_report_can_be_revoked(self):
        inspection = self._submitted()
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).action_revoke("early")

    def test_revoked_report_is_locked_and_final(self):
        inspection = self._approved()
        inspection.with_user(self.manager).action_revoke("issued in error")
        with self.assertRaises(UserError):
            inspection.with_user(self.manager).write({"review_notes": "edit"})
        with self.assertRaises(UserError):
            inspection.line_ids[:1].with_user(self.inspector).write({"result": "na"})
        for action in ("action_cancel", "action_reset_draft", "action_start"):
            with self.assertRaises(UserError):
                getattr(inspection.with_user(self.manager), action)()
        with self.assertRaises(AccessError):
            inspection.with_user(self.manager).write({"state": "approved"})

    def test_the_trailer_can_be_inspected_again(self):
        inspection = self._approved()
        inspection.with_user(self.manager).action_revoke("issued in error")
        corrected = self._draft(inspection_type="periodic")
        self.assertEqual(corrected.vin, inspection.vin)


class TestNonconformityFollowsTheFinding(IntegrityCase):

    def test_corrected_finding_closes_its_nonconformity(self):
        inspection = self._draft()
        inspection.with_user(self.inspector).action_start()
        self._complete_checklist(inspection)
        line = inspection.line_ids.filtered(
            lambda item: item.response_type == "choice" and item.criticality != "critical")[:1]
        line.write({"result": "no", "observation": "defect"})
        inspection.write({"inspector_signature": EVIDENCE})
        inspection.with_user(self.inspector).action_sign_inspector()
        inspection.with_user(self.inspector).action_submit()
        nonconformity = inspection.nonconformity_ids
        self.assertEqual(nonconformity.state, "open")

        inspection.with_user(self.reviewer).action_return_to_inspector()
        line.write({"result": "yes"})
        inspection.with_user(self.inspector).action_sign_inspector()
        inspection.with_user(self.inspector).action_submit()
        self.assertEqual(nonconformity.state, "closed")
        self.assertEqual(inspection.overall_result, "compliant")

    def test_only_a_reviewer_verifies_a_corrective_action(self):
        inspection = self._draft()
        line = inspection.line_ids[:1]
        line.write({"result": "no", "observation": "defect"})
        inspection._synchronize_nonconformities()
        nonconformity = inspection.nonconformity_ids
        nonconformity.write({"root_cause": "wear", "corrective_action": "replace"})
        with self.assertRaises(UserError):
            nonconformity.with_user(self.reviewer).action_verify()   # not submitted yet
        nonconformity.with_user(self.inspector).action_submit()
        with self.assertRaises(AccessError):
            nonconformity.with_user(self.inspector).action_verify()
        with self.assertRaises(AccessError):
            nonconformity.with_user(self.clerk).write({"state": "closed"})
        nonconformity.with_user(self.reviewer).action_verify()
        self.assertEqual(nonconformity.state, "verified")


@tagged("post_install", "-at_install")
class TestExpiredReportVerification(HttpCase, IntegrityCase):
    """Whoever scans the QR code must see that the validity has ended."""

    def test_expired_report_is_not_shown_as_valid(self):
        inspection = self._approved()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE trailer_inspection SET report_valid_until = %s WHERE id = %s",
            [fields.Date.today() - timedelta(days=1), inspection.id])
        inspection.invalidate_recordset()
        response = self.url_open("/trailer-inspection/verify/%s" % inspection.access_token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Expired", response.text)
        self.assertNotIn("صالح / Verified", response.text)

    def test_revoked_report_says_so_and_serves_no_pdf(self):
        inspection = self._approved()
        inspection.with_user(self.manager).action_revoke("issued in error")
        self.env.flush_all()
        response = self.url_open("/trailer-inspection/verify/%s" % inspection.access_token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Revoked", response.text)
        self.assertNotIn("صالح / Verified", response.text)
        self.assertNotIn("issued in error", response.text, "the internal reason is not published")
        pdf = self.url_open("/trailer-inspection/verify/%s/report" % inspection.access_token)
        self.assertEqual(pdf.status_code, 404)

    def test_current_report_is_verified(self):
        inspection = self._approved()
        self.env.flush_all()
        response = self.url_open("/trailer-inspection/verify/%s" % inspection.access_token)
        self.assertIn("صالح / Verified", response.text)
