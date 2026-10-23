# Odoo 19 -> 20 upgrade: status, findings and runbook

Branch: `codex/odoo20-readiness`. **This branch is Odoo 20 only** (`ir.access`, `get_str`,
`env.website`, `BinaryValue` do not exist in 19). Production stays on 19 until the gates below pass.

## Fresh tenants do not require a database upgrade

The existing customer databases are test data, so the supported first rollout is an isolated
**new-tenant plane** rather than an in-place major-version migration:

- the existing Odoo 19 control plane can keep accepting signups;
- `saas-tenant-provisioner.sh` creates every new tenant in `odoo_saas_postgres20` (PostgreSQL 16+);
- Community requests run in `odoo_saas_20_community`;
- Enterprise requests run in `odoo_saas_20_enterprise`, with an Odoo 20 Enterprise source mount;
- the generated certificate request carries `odoo_version=20`, so Nginx selects the Odoo 20 upstream;
- legacy certificate requests without a version continue to use their Odoo 19 upstream.

The Odoo 20 tenant plane is defined in `docker/odoo20/docker-compose.tenants.yml`. Copy
`docker/odoo20/.env.example` to a server-only `.env`, provide strong generated secrets, the existing
Docker network name, and the licensed Enterprise 20 source path. Install the four Odoo 20 Nginx
upstreams with `scripts/patch_nginx_odoo20_upstreams.sh`, then install the updated host provisioner.
The provisioner fails closed if the selected container is not Odoo 20 or PostgreSQL is below 16.

Activation must first be tested with a disposable signup on staging. Production activation still
requires explicit approval; it does not require uploading test customer databases to Odoo's upgrade
service.

## 1. What was verified (2026-10-23)

| Fact | Evidence |
|---|---|
| Odoo 20.0 is a final release | `odoo/release.py` on branch 20.0: `version_info = (20, 0, 0, 'final', 0, '')`; Docker Hub tags `20.0`, `20` |
| Python 3.12 - 3.14 | `MIN_PY_VERSION`/`MAX_PY_VERSION` in `release.py` |
| **PostgreSQL 16+ required** | Fresh DB on PG 15 fails (`any_value` does not exist); warning "Postgres version is 150019, lower than minimum required 160000" |
| **No Community 19->20 database migration path yet** | OCA/OpenUpgrade branch `20.0` has a single "Initial commit" (2026-09-28), no migration scripts; coverage page stops at 18->19 |
| Enterprise path (upgrade.odoo.com) | The official CLI was exercised against an isolated Enterprise copy without its filestore. The database has no embedded subscription code. A valid reference from the account's Odoo order was accepted, but Odoo classified it as `hosting: saas` and rejected target `20.0` for an external test upgrade. An Enterprise **On-Premise** contract, or written guidance from Odoo for this subscription, is required |

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
| Restore a real isolated Enterprise copy from PG 15 into staging PG 16 | **passes**: 629 public tables and 128 installed modules; production was not restarted or modified |
| Install 26 root custom modules, including the newly imported `saas_tenant_manager`, on a fresh Odoo 20 DB (`saas_restaurant_demo` excluded because it requires Enterprise) | **passes**, no ERROR/CRITICAL/Traceback and no targeted Odoo 20 compatibility warnings |
| `trailer_inspection_saso` tests on Odoo 20 | **79/79 pass** (76 existing + 3 new isolation tests) |
| HTTP smoke on Odoo 20: `/`, `/get-started`, `/web/login`, `/pricing`, `/faq`, `/about`, `/features`, `/contact`, `/apps`, `/industries`, `/industries/restaurants-cafes` | all 200; first CSS asset also 200; web log has no errors |
| Backend bundle compiles, includes trailer OWL code | yes |
| Docker image `docker/odoo20` builds | yes; includes `envsubst` and keeps Odoo's patched `wkhtmltopdf 0.12.6.1` |
| Desktop browser render of the restaurant industry page | page, hero image and assets render successfully on Odoo 20 |

**Not tested / not done** (do not read this branch as "upgrade complete"):

- Completing an existing-database upgrade: Community has no supported path, while the available Odoo
  subscription is an Online/SaaS contract and cannot authorize this external database upgrade.
- `saas_restaurant_demo` (needs Enterprise `account_accountant`); Enterprise image (`docker/enterprise`).
- Tests of the other 26 modules (they have none or were not run), portal isolation behaviour for
  `saas_portal`/`saas_reseller` beyond the converted CSV, payment/ZATCA/billing flows.
- Final RTL/mobile browser inspection. Arabic was loaded and attached to the isolated staging website, but
  the controlled browser session ended before the final responsive-layout capture.
- `/solutions` returns 404 on both the Odoo 20 smoke DB and the Odoo 19 production site, so it is not an
  Odoo 20 regression. `/trailer/verify` remains outside this smoke scope.
- `saas_website/views/page_about.xml` and `page_solutions.xml` contain unrelated user edits. The Odoo 20
  `t-esc` replacements were tested in staging, but those files must be reviewed/staged without absorbing
  unrelated work.
- Full provisioning integration tests. The known Odoo 20 API/CLI changes in host scripts and
  `remote_provisioning.py` were fixed, but no live tenant was provisioned from this branch.
- `Always-true` rule `Config: Super Admin Only` never restricted managers; that behaviour is preserved.
  Decide whether it should really be restricted.

## 4. Gates before any deployment

1. A supported database migration path for **every** tenant edition, proven on restored copies in staging.
   Today none exists for Community. Enterprise additionally requires an On-Premise contract accepted by
   `upgrade.odoo.com`; the available Online/SaaS subscription is not sufficient.
2. PostgreSQL 16+ in staging and production (separate, reversible migration: `pg_upgrade` or dump/restore).
3. `saas_tenant_manager` port reviewed, committed and covered by the same isolation checks as `saas_core`.
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
