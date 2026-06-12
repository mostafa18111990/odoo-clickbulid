# vendor/

Holds **external Odoo modules** that are required at build/test time but are
**not** part of this repository's own source.

## `saas_tenant_manager`

The pre-existing base module that every `saas_*` module depends on. Its source
of truth is the production server (`/opt/odoo-saas/addons/saas_tenant_manager`).

It is **not committed** here (see `.gitignore`). CI and local test runs obtain it
via `scripts/ci_fetch_base_module.sh`, which supports several strategies:

| Strategy | When to use | Config |
|---|---|---|
| Git submodule | Once the base module lives in its own git repo | `git submodule add <url> vendor/saas_tenant_manager` |
| Git clone | Base module in a (mono)repo, CI has a deploy key | `SAAS_BASE_MODULE_REPO`, `SAAS_BASE_MODULE_REF`, `SAAS_BASE_MODULE_PATH` |
| SCP from server | Quickest; server is source of truth | `SAAS_BASE_SSH_HOST`, `SAAS_BASE_SSH_PATH` (+ SSH key) |
| Manual vendor | One-off local dev | `scp -r root@HOST:/opt/.../saas_tenant_manager vendor/` |

### Quick local setup
```bash
# Easiest: pull it from the server once
scp -r root@129.121.98.243:/opt/odoo-saas/addons/saas_tenant_manager vendor/
# or use the helper (auto-detects strategy from env vars):
./scripts/ci_fetch_base_module.sh
```

### Promote to a proper submodule (recommended long-term)
Once `saas_tenant_manager` has its own git repository:
```bash
rm -rf vendor/saas_tenant_manager
git submodule add <repo-url> vendor/saas_tenant_manager
git commit -m "Vendor saas_tenant_manager as submodule"
```
`ci_fetch_base_module.sh` will then prefer the submodule automatically.
