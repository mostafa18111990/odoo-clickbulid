import re
from pathlib import Path

from odoo.tests.common import TransactionCase

JS_DIR = Path(__file__).resolve().parent.parent / "static" / "src"


class TestOwl3Components(TransactionCase):
    """Odoo 20 runs Owl 3, where a component declaring ``static props`` or
    ``static defaultProps`` raises as soon as it is instantiated. Python
    tests never execute the client code, so the home screen shipped broken
    once; this guard fails the build before that can happen again."""

    def test_no_component_declares_static_props(self):
        offenders = []
        for js in JS_DIR.rglob("*.js"):
            text = js.read_text(encoding="utf-8")
            if re.search(r"^\s*static\s+(props|defaultProps)\b", text, re.M):
                offenders.append(str(js.relative_to(JS_DIR)))
        self.assertFalse(
            offenders,
            "Use `props = useProps({...})` instead of static props in: %s" % ", ".join(offenders),
        )

    def test_home_action_does_not_use_removed_plugin(self):
        text = (JS_DIR / "js" / "trailer_home.js").read_text(encoding="utf-8")
        self.assertNotIn("ActionManagerPlugin", text)
        self.assertIn('useService("action")', text)
