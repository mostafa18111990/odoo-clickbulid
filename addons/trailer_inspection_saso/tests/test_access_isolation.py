from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_trailer_integrity import IntegrityCase, _vin


@tagged("post_install", "-at_install")
class TestCompanyIsolation(IntegrityCase):
    """The ir.access rows must keep every role inside its own companies,
    manager included: the manager's access implies the user's company limit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env["res.company"].create({"name": "Isolation Company B"})
        cls.own = cls._draft(cls, vin=cls.vin)
        cls.foreign = cls._draft(cls, vin=_vin("1M8GDM9A0KP042799"), company_id=cls.company_b.id)

    def test_user_and_manager_only_see_their_company(self):
        for role in (self.clerk, self.manager):
            visible = self.env["trailer.inspection"].with_user(role).search(
                [("id", "in", (self.own | self.foreign).ids)])
            self.assertEqual(visible, self.own, "%s sees another company's report" % role.login)

    def test_foreign_company_record_cannot_be_read_or_changed(self):
        for role in (self.clerk, self.manager):
            foreign = self.foreign.with_user(role)
            with self.assertRaises(AccessError):
                foreign.read(["name"])
            with self.assertRaises(AccessError):
                foreign.write({"inspection_location": "elsewhere"})
            with self.assertRaises(AccessError):
                foreign.unlink()

    def test_related_models_follow_the_company_limit(self):
        for model in ("trailer.inspection.nonconformity", "trailer.inspection.equipment",
                      "trailer.quality.document", "trailer.quality.complaint",
                      "trailer.vin.profile", "trailer.vin.sequence"):
            self.assertTrue(
                self.env["ir.access"].sudo().search([("model_id.model", "=", model), ("domain", "!=", False)]),
                "%s lost its company domain" % model)
