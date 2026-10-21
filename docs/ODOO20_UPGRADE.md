# Odoo 19 -> 20 upgrade: status, findings and runbook

Branch: `codex/odoo20-readiness`. **This branch is Odoo 20 only** (`ir.access`, `get_str`,
`env.website`, `BinaryValue` do not exist in 19). Production stays on 19 until the gates below pass.

## 1. What was verified (2026-10-21)

| Fact | Evidence |
|---|---|
| Odoo 20.0 is a final release | `odoo/release.py` on branch 20.0: `version_info = (20, 0, 0, 'final', 0, '')`; Docker Hub tags `20.0`, `20` |
| Python 3.12 - 3.14 | `MIN_PY_VERSION`/`MAX_PY_VERSION` in `release.py` |
| **PostgreSQL 16+ required** | Fresh DB on PG 15 fails (`any_value` does not exist); warning "Postgres version is 150019, lower than minimum required 160000" |
| **No Community 19->20 database migration path yet** | OCA/OpenUpgrade branch `20.0` has a single "Initial commit" (2026-09-28), no migration scripts; coverage page stops at 18->19 |
| Enterprise path (upgrade.odoo.com) | **Not verified** - the docs page could not be read in full. Needs an Enterprise subscription check by the account owner |

Changing the image tag and running `-u` does **not** migrate a database across major versions.

## 2. Findings and fixes in this branch

Each item was found by installing on `odoo:20.0` (fresh DB, PG 16) and fixed with Odoo's own
`upgrade_code` scripts where one exists.

| Severity | Finding | Fix |
|---|---|---|
| Critical | `ir.model.access` + `ir.rule` removed, replaced by `ir.access` (company/portal/reseller isolation lives here) | 233 ACL rows -> `security/ir.access.csv`; 27 group rules folded into `domain` on the matching rows; 7 always-true rules (`[(1,'=',1)]`) dropped (they never restricted). Verified by `test_access_isolation.py`, which fails if a role loses its company domain (mutation-checked) |
| Critical | `_sql_constraints` ignored (warning only): unique constraints silently lost | converted to `models.Constraint` (official script) |
| Critical | `t-esc` is an unknown QWeb directive: values silently disappear | `t-out` in 21 template files |
| High | `ir.config_parameter.get_param/set_param` removed | `get_str/set_str` (10 files) |
| High | Binary fields reject `bytes`, return `BinaryValue` | `.decode()` on writes, `.content` on read (trailer) |
| High | `website.get_current_website()` removed | `self.env.website` |
| High | `odoo.http.content_disposition` moved | import from `odoo.http.stream` |
| Medium | `report_file` removed from `ir.actions.report` | field dropped |
| Medium | OWL 3 | `trailer_home.js/.xml` migrated with `owl3-migration` |
| Existing bug | `groups_id` used on `res.users.create` (19 already uses `group_ids`) | fixed in `saas_portal`, `saas_reseller` |

## 3. Test results

| Check | Result |
|---|---|
| Install 27 modules (26 in repo minus `saas_restaurant_demo`, plus trailer and external `saas_tenant_manager`) on fresh Odoo 20 DB | **passes**, no ERROR/CRITICAL |
| `trailer_inspection_saso` tests on Odoo 20 | **79/79 pass** (76 existing + 3 new isolation tests) |
| HTTP smoke on Odoo 20: `/`, `/get-started`, `/web/login`, `/pricing`, `/faq`, `/about`, `/features`, `/contact` | 200 |
| Backend bundle compiles, includes trailer OWL code | yes |
| Docker image `docker/odoo20` builds | yes |

**Not tested / not done** (do not read this branch as "upgrade complete"):

- Upgrading any existing database (no supported Community path; Enterprise path unverified).
- `saas_restaurant_demo` (needs Enterprise `account_accountant`); Enterprise image (`docker/enterprise`).
- Tests of the other 26 modules (they have none or were not run), portal isolation behaviour for
  `saas_portal`/`saas_reseller` beyond the converted CSV, payment/ZATCA/billing flows.
- OWL home screen and RTL/mobile layout in a real browser (browser pane was unavailable).
- `/solutions` returns 404 and `/trailer/verify` 404 on the smoke DB; not checked against Odoo 19 behaviour.
- **`saas_tenant_manager` is not in this repo** (lives only on the server). It must get the same
  `ir.access` conversion and `_sql_constraints` fix before Odoo 20 can load `saas_core`.
- `saas_website/views/page_about.xml` and `page_solutions.xml` had uncommitted edits at the time and were
  left alone: `page_solutions.xml` still contains 28 `t-esc`, which Odoo 20 silently ignores. Commit those
  edits, then run `sed -i 's/ t-esc=/ t-out=/g'` on them.
- Host scripts and provisioner under `scripts/` (they `docker exec ... odoo -u`, call `set_param`, use
  `odoo:19` images, PG 15) and `remote_provisioning.py` line 241 (`set_param` sent to remote tenants).
- `Always-true` rule `Config: Super Admin Only` never restricted managers; that behaviour is preserved.
  Decide whether it should really be restricted.

## 4. Gates before any deployment

1. A supported database migration path for **every** tenant edition (Community and Enterprise), proven on a
   restored copy of real data in staging. Today none exists for Community.
2. PostgreSQL 16+ in staging and production (separate, reversible migration: `pg_upgrade` or dump/restore).
3. `saas_tenant_manager` ported and in git.
4. Staging smoke: public routes, login, Odoo logs, assets, Arabic/RTL, mobile, integrations, tenant isolation.
5. Explicit user approval **and** GitHub `production` environment approval (a merge is not approval).

## 5. Upgrade runbook (NOT executed - for staging first)

1. Freeze provisioning; announce a maintenance window.
2. Backup (timestamped, verified): all databases (`pg_dump -Fc`), filestore, deployed `addons/`, checksums of
   `nginx.conf`, `odoo.conf`, compose files. Restore one dump into a scratch DB and run a count check.
3. Upgrade PostgreSQL to 16 (staging first), verify `SELECT version()` and DB list.
4. Build `docker/odoo20` image; start staging with it against **restored copies**, never live DBs.
5. Per database, only via the supported route for its edition; then `-u all` with `--stop-after-init`,
   grep the log for `ERROR|CRITICAL|Traceback`. Any hit stops the rollout.
6. Smoke tests (section 4.4) and tenant isolation checks (portal user sees only their own records).

## 6. Rollback

Keep the 19 image tag, 19 addons and the pre-upgrade backup untouched.
If any upgrade step or smoke test fails: stop the Odoo 20 containers, restore PG 15 data (or the dump into the
old PG), restore the filestore and the 19 `addons/`, restart the 19 stack, repeat the smoke tests, then
record the failure. Rollback must be rehearsed in staging before production is considered.
