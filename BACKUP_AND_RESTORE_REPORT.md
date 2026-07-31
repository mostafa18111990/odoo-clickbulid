# ClickBuild Baseline Backup and Restore Report

## Result

Status: **PASS — full baseline backup created, validated and restored successfully in an isolated test environment.**

No redesign, content, application, database, DNS or production deployment change was performed.

## Backup identity

- Name: `clickbuild-production-before-redesign-2026-07-31-0843`
- Created: 2026-07-31 08:43 UTC / 11:43 Asia/Riyadh
- Server path: `/opt/backups/clickbuild-production-before-redesign-2026-07-31-0843`
- Total size at initial validation: 6.3 GB
- Protection: outside the project directory; restricted to the server administrator.
- Free server storage after backup and restore test: approximately 139 GB.

## Coverage

- 42 non-template PostgreSQL databases; every dump passed `pg_restore --list`.
- Community, Enterprise and existing staging Odoo data/filestore archives.
- Production and staging project source, standard/custom/OCA/Cybrosys addons, themes, templates, website assets and scripts.
- Customer export artifacts.
- Docker Compose/container/network/volume definitions and exact runtime images.
- Nginx, TLS/Let's Encrypt, systemd, cron, host and resolver configuration.
- Read-only DNS/TLS documentation.
- Odoo, Python, PostgreSQL, Nginx, installed packages and Python library versions.
- Functional snapshots for pages, products, pricelists, attachments, mail servers and payment providers; CRM is recorded as not installed in the central management database.

Sensitive configuration was archived under root-only permissions and is not reproduced in this report.

## Restore test

- Environment: disposable Docker network, PostgreSQL container, restored database, Odoo container and isolated data directory.
- Exposure: localhost only.
- Restored database: central Odoo management database.
- Restored filestore: matching Community filestore.
- Odoo version: 19.0-20260528.
- PostgreSQL version: 15.18.
- Installed modules loaded: 84.
- Database size after restore: 93,371,751 bytes.
- Restored filestore sample: 474 files, 25,990,050 bytes for the tested database.
- Login page: HTTP 200.
- Home page: HTTP 200.
- Administrator authentication: PASS.
- Stored attachment from restored Filestore: HTTP 200.
- Functional record-count comparison: MATCH.
- Measured duration: 101 seconds.
- Production containers/databases/files modified: NO.
- Cleanup of test environment: PASS.

Evidence is stored in `RESTORE_TEST_EVIDENCE.log` and `RESTORE_TEST_REPORT.md` inside the protected backup.

## Git rollback point

- Baseline commit: `0aa1b6d960c6f5169055b0bcc61c2ba385c58c35`
- Protected branch: `codex/production-before-clickbuild-3`
- Protected annotated tag: `production-before-clickbuild-3`

The project contained many pre-existing untracked working artifacts. They were not deleted, staged or committed. The complete production filesystem is preserved by the server-side code archive.

## Approval gate

Per the mandatory instruction, development must remain stopped until the owner explicitly confirms receipt of:

1. Backup path and size.
2. Final checksum.
3. Restore test report/evidence.
4. `ROLLBACK_PLAN.md`.
5. Git branch and tag.

