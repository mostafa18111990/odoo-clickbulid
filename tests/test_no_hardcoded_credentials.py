"""Regression checks for credentials accidentally committed to maintenance scripts."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

PATTERNS = {
    "credential variable assigned a literal": re.compile(
        r"(?im)^\s*[A-Za-z_][A-Za-z0-9_]*(?:pass|password|passwd|secret|token|api_key)"
        r"[A-Za-z0-9_]*\s*=\s*(['\"])(?!\$|\{|<|__|True|False|dummy|example)[^'\"\r\n]{4,}\1"
    ),
    "literal password passed to a client": re.compile(
        r"(?i)password\s*=\s*(['\"])(?!\$|\{|<|__|True|False|dummy|example)[^'\"\r\n]{4,}\1"
    ),
    "literal PGPASSWORD value": re.compile(
        r"(?i)PGPASSWORD\s*=\s*(?!\$|\{|<|__|DB_PASS\b)[^\s'\";\\]{4,}"
    ),
    "literal Odoo/database config password": re.compile(
        r"(?im)^\s*(?:db_password|admin_passwd|master_password)\s*=\s*"
        r"(?!\$|\{|<|__)[^\s#;\r\n]{4,}"
    ),
    "private key material": re.compile(
        r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
    ),
}


def test_maintenance_scripts_contain_no_hardcoded_credentials():
    findings = []
    for path in sorted(SCRIPTS.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".sh", ".ps1"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for description, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {description}")

    assert not findings, "Hardcoded credentials detected:\n" + "\n".join(findings)
