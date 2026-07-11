from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from ..models.trailer_vin import calculate_vin_check_digit


class TestTrailerInspection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        inspector_group = cls.env.ref("trailer_inspection_saso.group_trailer_inspector")
        reviewer_group = cls.env.ref("trailer_inspection_saso.group_trailer_reviewer")
        cls.inspector = cls.env["res.users"].create(
            {
                "name": "Trailer Inspector",
                "login": "trailer.inspector.test",
                "group_ids": [Command.link(inspector_group.id)],
            }
        )
        cls.reviewer = cls.env["res.users"].create(
            {
                "name": "Technical Reviewer",
                "login": "trailer.reviewer.test",
                "group_ids": [Command.link(reviewer_group.id)],
            }
        )
        cls.authorization = cls.env["trailer.inspector.authorization"].create(
            {
                "user_id": cls.inspector.id,
                "authorization_number": "AUTH-TEST-001",
                "valid_from": fields.Date.today() - timedelta(days=30),
                "valid_to": fields.Date.today() + timedelta(days=365),
            }
        )

    def _inspection_values(self):
        return {
            "partner_id": self.env.company.partner_id.id,
            "inspection_location": "Test Inspection Center",
            "inspector_id": self.inspector.id,
            "reviewer_id": self.reviewer.id,
            "product_description": "O3 semi-trailer",
            "trailer_type": "semi_trailer",
            "category": "o3",
            "vin": "1M8GDM9AXKP042788",
            "manufacturer_name": "Test Manufacturer",
            "impartiality_confirmed": True,
        }

    def test_checklist_is_generated_and_result_is_computed(self):
        inspection = self.env["trailer.inspection"].create(self._inspection_values())
        self.assertTrue(inspection.line_ids)
        inspection.line_ids.write({"result": "yes"})
        self.assertEqual(inspection.overall_result, "compliant")
        failed_line = inspection.line_ids[0]
        failed_line.write({"result": "no", "observation": "Measured value exceeds limit"})
        self.assertEqual(inspection.overall_result, "non_compliant")
        self.assertEqual(inspection.nonconformity_count, 1)

    def test_vin_validation(self):
        values = self._inspection_values()
        values["vin"] = "INVALIDVIN"
        with self.assertRaises(ValidationError):
            self.env["trailer.inspection"].create(values)

    def test_vin_check_digit_validation(self):
        self.assertEqual(calculate_vin_check_digit("1M8GDM9AXKP042788"), "X")
        values = self._inspection_values()
        values["vin"] = "1M8GDM9A1KP042788"
        with self.assertRaises(ValidationError):
            self.env["trailer.inspection"].create(values)

    def test_gso_vin_generation(self):
        profile = self.env["trailer.vin.profile"].create({
            "name": "Test Trailer Manufacturer",
            "manufacturer_id": self.env.company.partner_id.id,
            "wmi": "1M9",
            "vds": "AA11A",
            "plant_code": "A",
            "wmi_certificate_number": "WMI-TEST-001",
            "wmi_certificate": "VGVzdA==",
            "assignment_authority_confirmed": True,
        })
        profile.action_approve()
        vin = profile.generate_vin(2026)
        self.assertEqual(len(vin), 17)
        self.assertEqual(vin[8], calculate_vin_check_digit(vin))
        self.assertEqual(vin[9], "T")
        self.assertEqual(vin[10], "A")
        self.assertTrue(vin.endswith("000001"))

    def test_reviewer_must_be_independent(self):
        values = self._inspection_values()
        values["reviewer_id"] = self.inspector.id
        with self.assertRaises(ValidationError):
            self.env["trailer.inspection"].create(values)

    def test_start_requires_valid_authorization(self):
        inspection = self.env["trailer.inspection"].with_user(self.inspector).create(
            self._inspection_values()
        )
        inspection.action_start()
        self.assertEqual(inspection.state, "in_progress")
        self.assertEqual(inspection.authorization_id, self.authorization)

    def test_submit_rejects_incomplete_checklist(self):
        inspection = self.env["trailer.inspection"].with_user(self.inspector).create(
            self._inspection_values()
        )
        inspection.action_start()
        with self.assertRaises(UserError):
            inspection.action_submit()

    def test_nonconformity_and_reinspection(self):
        inspection = self.env["trailer.inspection"].create(self._inspection_values())
        inspection.line_ids.write({"result": "yes"})
        failed_line = inspection.line_ids[0]
        failed_line.write({"result": "no", "observation": "Brake result outside limit"})
        inspection._synchronize_nonconformities()
        self.assertEqual(len(inspection.nonconformity_ids), 1)
        action = inspection.action_create_reinspection()
        reinspection = self.env["trailer.inspection"].browse(action["res_id"])
        self.assertEqual(reinspection.inspection_type, "reinspection")
        self.assertEqual(reinspection.parent_inspection_id, inspection)
        self.assertEqual(len(reinspection.line_ids), 1)

    def test_approved_report_is_locked(self):
        inspection = self.env["trailer.inspection"].create(self._inspection_values())
        inspection.state = "approved"
        with self.assertRaises(UserError):
            inspection.write({"vin": "1M8GDM9AXKP042789"})

    def test_numeric_rule_engine(self):
        inspection = self.env["trailer.inspection"].create(self._inspection_values())
        numeric_line = inspection.line_ids.filtered(lambda line: line.response_type == "numeric")[:1]
        if numeric_line:
            numeric_line.write({"measured_value": numeric_line.maximum_value + 1})
            numeric_line._evaluate_measurements()
            self.assertEqual(numeric_line.result, "no")
