# ClickBuild SaaS — Master Deployment Runbook

**Version:** 19.0 · **Target:** Odoo 19 Community · **VPS:** 129.121.98.243
**Scope:** Deploy all 19 `saas_*` modules + FastAPI bridge + observability stack from a clean or existing server.

> Read this top-to-bottom the first time. For redeploys, jump to §9 (Quick Redeploy).

---

## 0. CONVENTIONS

| Symbol | Meaning |
|---|---|
| `[VPS]` | Run on the server (SSH) |
| `[ODOO]` | Run inside the Odoo container |
| `[LOCAL]` | Run on your machine |
| `⚠️` | Must verify before continuing |
| `✅` | Smoke test / checkpoint |

**Key paths**
```
/opt/odoo-saas/addons/          → all saas_* modules
/opt/odoo-saas/backend/         → FastAPI app
/opt/clickbuild/data/<db>/      → per-tenant Odoo filestore
/etc/nginx/sites-available/     → nginx vhosts
Container: odoo_saas_app        → shared Odoo
DB: odoo_master                 → SaaS master database
```

---

## 1. PRE-FLIGHT CHECKLIST

⚠️ Confirm ALL before starting:

- [ ] SSH access to `root@129.121.98.243`
- [ ] DNS wildcard `*.clickbuild.com` → `129.121.98.243` (A record) is live
      Verify: `dig +short test123.clickbuild.com` returns the IP
- [ ] Docker + Docker Compose installed (`docker --version`, `docker compose version`)
- [ ] PostgreSQL 15+ reachable; `odoo_master` DB exists
- [ ] Redis running with a password
- [ ] Nginx installed with `stub_status` capability
- [ ] `certbot` + `python3-certbot-nginx` installed (for custom domains)
- [ ] Backup of current `odoo_master` taken (see §8)
- [ ] Maintenance window scheduled (module install requires Odoo restart)

```bash
# [VPS] One-shot prerequisite check
for c in docker certbot nginx psql redis-cli dig; do
  command -v $c >/dev/null && echo "✅ $c" || echo "❌ MISSING: $c"
done
docker ps --format '{{.Names}}' | grep -q odoo_saas_app && echo "✅ odoo container" || echo "❌ odoo container not running"
```

---

## 2. PYTHON DEPENDENCIES

### 2.1 Odoo container deps

```bash
# [ODOO] All third-party libs used across the 19 modules
docker exec odoo_saas_app pip3 install \
  requests \
  python-dateutil \
  dnspython \
  pyotp \
  qrcode \
  Pillow \
  stripe
```

| Library | Used by | Purpose |
|---|---|---|
| `requests` | core (bridge), payment, marketplace, domain, api, monitoring | HTTP to FastAPI + gateways |
| `python-dateutil` | subscription | `relativedelta` for billing periods |
| `dnspython` | domain_manager | read-only DNS verification |
| `pyotp` | security | TOTP 2FA |
| `qrcode` + `Pillow` | security | 2FA enrollment QR |
| `stripe` | payment | Stripe gateway (optional) |

✅ **Checkpoint:** `docker exec odoo_saas_app python3 -c "import requests, dateutil, dns, pyotp, qrcode; print('deps ok')"`

### 2.2 FastAPI backend deps

```bash
# [VPS] Add to backend/requirements.txt (already has fastapi, sqlalchemy, docker, etc.)
# New for bridge endpoints — usually already present:
#   requests (for callbacks), docker (SDK), psycopg2-binary
cd /opt/odoo-saas/backend && pip3 install -r requirements.txt
```

### 2.3 VPS host deps (custom domain SSL)

```bash
# [VPS]
apt-get update && apt-get install -y certbot python3-certbot-nginx
```

---

## 3. UPLOAD MODULES (exact order not required — dependency graph handles it)

```bash
# [LOCAL] Upload all 19 modules
MODULES="saas_core saas_lifecycle saas_subscription saas_billing saas_payment \
saas_portal saas_website saas_domain_manager saas_notifications saas_marketplace \
saas_reseller saas_support saas_knowledge saas_marketing saas_reporting \
saas_api saas_security saas_ai saas_monitoring"

for m in $MODULES; do
  scp -r "$m/" root@129.121.98.243:/opt/odoo-saas/addons/
done

# [VPS] Fix ownership + permissions
ssh root@129.121.98.243 \
  "chown -R odoo:odoo /opt/odoo-saas/addons/ && chmod -R 755 /opt/odoo-saas/addons/"
```

⚠️ Confirm `saas_tenant_manager` (the pre-existing base module) is already installed and working before proceeding — every new module depends on it transitively.

---

## 4. INSTALL MODULES (single command — dependency-ordered)

Installing the **last** module (`saas_monitoring`) auto-installs all 18 dependencies in the correct order.

```bash
# [ODOO] Update module list first
docker exec odoo_saas_app odoo \
  --config=/etc/odoo/odoo.conf \
  --database=odoo_master \
  --update=base \
  --stop-after-init

# [ODOO] Install everything via the leaf module
docker exec odoo_saas_app odoo \
  --config=/etc/odoo/odoo.conf \
  --database=odoo_master \
  --init=saas_monitoring \
  --stop-after-init

# [VPS] Restart
docker restart odoo_saas_app
```

> If you prefer **phased install** (recommended for first deploy, to catch errors early):
```bash
for m in saas_core saas_lifecycle saas_subscription saas_billing saas_payment \
         saas_portal saas_website saas_domain_manager saas_notifications \
         saas_marketplace saas_reseller saas_support saas_knowledge \
         saas_marketing saas_reporting saas_api saas_security saas_ai saas_monitoring; do
  echo "=== Installing $m ==="
  docker exec odoo_saas_app odoo --config=/etc/odoo/odoo.conf \
    --database=odoo_master --init=$m --stop-after-init || { echo "❌ FAILED at $m"; break; }
done
docker restart odoo_saas_app
```

✅ **Checkpoint:** Log into Odoo. The left menu shows **ClickBuild SaaS** with sub-menus: Analytics, Monitoring, Tenants, Subscriptions, Billing, Marketplace, Resellers, Support, Knowledge Base, Marketing, Notifications, Configuration.

---

## 5. CONFIGURATION PARAMETERS

All configured in **ClickBuild SaaS → Configuration**. Set these in order.

### 5.1 Platform Settings (`saas.config`)
*Configuration → Platform Settings*

| Field | Value | Notes |
|---|---|---|
| Platform Name | `ClickBuild` | Shown on emails/invoices |
| Platform Domain | `clickbuild.com` | |
| FastAPI Base URL | `http://127.0.0.1:8000` | Internal |
| API Internal Token | *(generate)* | `python3 -c "import secrets;print(secrets.token_urlsafe(48))"` — **must match FastAPI `.env` `INTERNAL_API_TOKEN`** |
| Webhook Secret | *(generate)* | `python3 -c "import secrets;print(secrets.token_hex(32))"` — **must match FastAPI `.env` `ODOO_WEBHOOK_SECRET`** |
| Use FastAPI Bridge | ✅ True | |
| Trial Days | `14` | |
| Grace Period Days | `3` | |
| Archive Retention Days | `90` | |
| Company VAT Number | `3XXXXXXXXXXXXX3` | 15-digit Saudi VAT (ZATCA) |
| Support Email | `support@clickbuild.com` | |

### 5.2 Tax Rates (`saas.tax.rate`)
*Configuration → Tax Rates* — 7 MENA rates auto-loaded. Verify SA=15%, AE=5%, EG=14%. Add your **Tax Registration Number** per jurisdiction.

### 5.3 Payment Gateways (`saas.payment.gateway`)
*Billing → Payment Gateways* — all disabled by default. For each you use:

| Gateway | Required fields |
|---|---|
| PayTabs | `profile_id`, `api_key` (server key), `webhook_secret` |
| PayMob | `api_key`, `webhook_secret` (HMAC), `extra_config` (integration IDs, iframe_id) |
| Stripe | `api_key` (secret), `api_key_2` (publishable), `webhook_secret` |
| HyperPay | `api_key` (access token), `profile_id` (entity ID), `extra_config` (mada/applepay entity IDs) |
| MyFatoorah | `api_key`, `webhook_secret` |

Then: untick **Sandbox**, tick **Enabled**. Register webhook URLs (§7.2).

### 5.4 SMS Gateway (`saas.sms.gateway`) — optional
*Configuration → SMS Gateways* — add Unifonic/Twilio/Taqnyat credentials + sender ID.

### 5.5 AI Provider (`saas.ai.provider`) — optional
*Configuration → AI → AI Providers* — default is **Null (fallback)**, platform works without AI. To enable: open OpenAI/Anthropic/Local, add key, tick Active + Default.

### 5.6 Security Policy (`saas.security.setting`)
*Configuration → Security → Security Settings* — defaults are sane (2FA enforced for admins, 5-attempt lockout). Review password policy.

### 5.7 Metrics token (monitoring)
The Prometheus scrape uses the **same** `API Internal Token` as `?token=`. No separate config.

### 5.8 Platform IP (domain manager)
*Settings → Technical → System Parameters*: confirm `saas_domain.platform_ip` = `129.121.98.243`.

✅ **Checkpoint:** Configuration → Platform Settings shows no "Action Required" banner (token + webhook secret set).

---

## 6. FASTAPI BACKEND DEPLOYMENT

The Odoo modules delegate provisioning/SSL/app-install/health to FastAPI. Deploy the new bridge endpoints (see `backend/app/api/v1/endpoints/bridge.py` and `domains.py`).

```bash
# [VPS] Set environment in backend/.env
cat >> /opt/odoo-saas/backend/.env <<'EOF'
INTERNAL_API_TOKEN=<same as saas.config API Internal Token>
ODOO_WEBHOOK_SECRET=<same as saas.config Webhook Secret>
ODOO_WEBHOOK_URL=http://127.0.0.1:8069/saas/core/webhook/provisioning
EOF

# [VPS] Restart FastAPI (systemd or container)
systemctl restart clickbuild-api   # or: docker restart clickbuild_api
```

✅ **Checkpoint:**
```bash
curl -s http://127.0.0.1:8000/api/health   # → {"status":"ok",...}
# Authenticated bridge ping:
curl -s http://127.0.0.1:8000/api/v1/bridge/ping \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN"   # → {"status":"ok"}
```

---

## 7. NGINX + WEBHOOKS + SSL

### 7.1 Nginx routes (verify present)
```
clickbuild.com          → Odoo website (:8069)   [public site, /docs, /my, /api/saas]
api.clickbuild.com      → FastAPI (:8000)
grafana.clickbuild.com  → Grafana (:3001)         [admin only]
*.clickbuild.com        → per-tenant containers (:8100-9000, dynamic)
```
Add Nginx `stub_status` for the nginx_exporter:
```nginx
# in the default server block
location /stub_status { stub_status; allow 127.0.0.1; deny all; }
```
Reload: `nginx -t && nginx -s reload`

### 7.2 Register payment webhooks (in each gateway dashboard)
```
PayTabs:    https://clickbuild.com/saas/payment/paytabs/webhook
PayMob:     https://clickbuild.com/saas/payment/paymob/webhook
Stripe:     https://clickbuild.com/saas/payment/stripe/webhook
HyperPay:   https://clickbuild.com/saas/payment/hyperpay/webhook
MyFatoorah: https://clickbuild.com/saas/payment/myfatoorah/webhook
```

### 7.3 Platform SSL
Ensure `clickbuild.com` + `*.clickbuild.com` wildcard cert exists (Let's Encrypt DNS-01 for wildcard):
```bash
certbot certonly --manual --preferred-challenges dns \
  -d clickbuild.com -d '*.clickbuild.com'
```

---

## 8. OBSERVABILITY STACK

```bash
# [VPS]
cd /opt/odoo-saas/addons/saas_monitoring/infra
export ODOO_METRICS_TOKEN="<saas.config API Internal Token>"
export GRAFANA_PASSWORD="<strong-password>"
export PG_EXPORTER_DSN="postgresql://odoo:PASS@localhost:5432/postgres?sslmode=disable"
export REDIS_PASSWORD="<redis-password>"

docker compose -f docker-compose.monitoring.yml up -d
docker compose -f docker-compose.monitoring.yml ps
```

✅ **Checkpoint:**
```bash
curl -s "http://127.0.0.1:8069/saas/metrics?token=$ODOO_METRICS_TOKEN" | head -5
# → # HELP saas_mrr ...
curl -s http://127.0.0.1:9090/-/healthy   # Prometheus → Healthy
# Grafana: https://grafana.clickbuild.com → "ClickBuild — Platform Overview"
```

---

## 9. SMOKE TESTS (end-to-end)

Run after every deploy. Each must pass.

### 9.1 Module integrity
```bash
docker exec odoo_saas_app odoo shell --config=/etc/odoo/odoo.conf -d odoo_master <<'PY'
mods = env['ir.module.module'].search([('name','like','saas_'),('state','=','installed')])
print('Installed saas_* modules:', len(mods))
assert len(mods) >= 19, 'MISSING MODULES'
print('✅ all modules installed')
PY
```

### 9.2 Public website
```bash
curl -sf https://clickbuild.com/            > /dev/null && echo "✅ homepage"
curl -sf https://clickbuild.com/pricing     > /dev/null && echo "✅ pricing (live plans)"
curl -sf https://clickbuild.com/docs        > /dev/null && echo "✅ knowledge base"
curl -sf https://clickbuild.com/get-started > /dev/null && echo "✅ signup funnel"
```

### 9.3 Signup → provision (creates a real test tenant)
```bash
curl -s -X POST https://clickbuild.com/get-started/check \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"call","params":{"subdomain":"smoketest-001"}}'
# → {"result":{"available":true,...}}
# Then complete signup in UI; verify tenant appears in:
#   ClickBuild SaaS → Tenants  (state: trial)
#   and https://smoketest-001.clickbuild.com resolves
```

### 9.4 Billing chain
```bash
# In Odoo shell: generate a renewal invoice for a test subscription
docker exec odoo_saas_app odoo shell --config=/etc/odoo/odoo.conf -d odoo_master <<'PY'
sub = env['saas.subscription'].search([('status','in',('trial','active'))], limit=1)
if sub:
    from odoo.addons.saas_billing.services.invoice_service import InvoiceService
    inv = InvoiceService(env).generate_renewal_invoice(sub.id)
    print('✅ invoice', inv.number if inv else 'none', 'tax:', inv.amount_tax if inv else 0)
PY
```

### 9.5 API
```bash
# Create an API key in portal (/my/saas/api) then:
curl -s https://clickbuild.com/api/saas/v1/me \
  -H "Authorization: Bearer cb_live_YOURKEY" | python3 -m json.tool
# → {"key_name":..., "rate_limit":{"limit":1000,...}}
```

### 9.6 Metrics + health
```bash
curl -sf http://127.0.0.1:8069/saas/health | grep -q '"status"' && echo "✅ health endpoint"
curl -s "http://127.0.0.1:8069/saas/metrics?token=$ODOO_METRICS_TOKEN" | grep -q saas_mrr && echo "✅ prometheus metrics"
```

### 9.7 Cron jobs active
```bash
docker exec odoo_saas_app odoo shell --config=/etc/odoo/odoo.conf -d odoo_master <<'PY'
crons = env['ir.cron'].search([('name','like','SaaS')])
print('SaaS cron jobs:', len(crons), '— active:', len(crons.filtered('active')))
PY
```

### 9.8 Tenant isolation (critical security)
```bash
docker exec odoo_saas_app odoo shell --config=/etc/odoo/odoo.conf -d odoo_master <<'PY'
from odoo.addons.saas_security.services.isolation_validator_service import IsolationValidatorService
r = IsolationValidatorService(env).validate()
print('Isolation passed:', r['passed'], '| missing rules:', r['rules_missing'])
assert r['passed'], '❌ ISOLATION BREACH'
print('✅ tenant isolation intact')
PY
```

---

## 10. AUTOMATED TEST SUITE (run in staging before prod)

```bash
docker exec odoo_saas_app odoo \
  --config=/etc/odoo/odoo.conf \
  --database=odoo_master_test \
  --test-enable \
  --test-tags=/saas_core,/saas_subscription,/saas_billing,/saas_payment,/saas_portal,/saas_security,/saas_reporting,/saas_api \
  --init=saas_monitoring \
  --stop-after-init 2>&1 | grep -E "(FAILED|ERROR|passed|tests)"
```

---

## 11. ROLLBACK

```bash
# 1. Restore DB backup
docker exec odoo_saas_app pg_restore -d odoo_master /backups/odoo_master_PREDEPLOY.dump --clean

# 2. Revert addons (keep timestamped copies)
ssh root@129.121.98.243 "rm -rf /opt/odoo-saas/addons/saas_* && cp -r /opt/backups/addons_PREDEPLOY/* /opt/odoo-saas/addons/"

# 3. Restart
docker restart odoo_saas_app
```

> **Backup before every deploy:**
> ```bash
> docker exec odoo_saas_app pg_dump -Fc odoo_master > /backups/odoo_master_$(date +%F).dump
> cp -r /opt/odoo-saas/addons /opt/backups/addons_$(date +%F)
> ```

---

## 12. QUICK REDEPLOY (subsequent updates)

```bash
# [LOCAL] sync changed module(s)
scp -r saas_billing/ root@129.121.98.243:/opt/odoo-saas/addons/

# [VPS] backup → upgrade module → restart
ssh root@129.121.98.243 '
  docker exec odoo_saas_app pg_dump -Fc odoo_master > /backups/odoo_master_$(date +%F_%H%M).dump
  chown -R odoo:odoo /opt/odoo-saas/addons/saas_billing
  docker exec odoo_saas_app odoo --config=/etc/odoo/odoo.conf -d odoo_master -u saas_billing --stop-after-init
  docker restart odoo_saas_app
'
```

---

## 13. POST-DEPLOY OPERATIONAL CHECKLIST

- [ ] All §9 smoke tests green
- [ ] Grafana dashboard receiving data (MRR panel non-empty after first snapshot)
- [ ] First metric snapshot generated (run "Monthly Metric Snapshot" cron manually once)
- [ ] Test payment in sandbox → invoice marked paid → notification sent
- [ ] Test custom domain on a tenant (Business plan) → SSL issued
- [ ] 2FA enrollment works on an admin account
- [ ] Isolation validation cron green (no critical audit alerts)
- [ ] Set marketing spend param for CAC: `saas_reporting.monthly_marketing_spend`
- [ ] Backup cron verified (daily `pg_dump`)

---

---

## 14. CI/CD — REQUIRED SECRETS & VARIABLES

Set these in GitHub → repo → Settings → Secrets and variables → Actions.

### Secrets
| Name | Purpose |
|---|---|
| `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY` | Staging deploy SSH |
| `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY` | Production deploy SSH |
| `SAAS_BASE_SSH_KEY` | SSH key to SCP `saas_tenant_manager` from server (if using SCP strategy) |
| `SAAS_BASE_SSH_HOST` | e.g. `root@129.121.98.243` (SCP strategy) |
| `SAAS_BASE_MODULE_REPO` | git URL of base module (if using clone/submodule strategy) |

### Variables
| Name | Example |
|---|---|
| `SAAS_BASE_SSH_PATH` | `/opt/odoo-saas/addons/saas_tenant_manager` |
| `SAAS_BASE_MODULE_REF` | `main` |

### Base-module strategy (pick one)
`saas_tenant_manager` is the pre-existing base dependency, not part of this repo's source. CI obtains it via `scripts/ci_fetch_base_module.sh` using whichever strategy you configure:

1. **Submodule (recommended long-term):** once it has its own repo —
   `git submodule add <url> vendor/saas_tenant_manager`. CI's `checkout` with
   `submodules: recursive` handles the rest.
2. **Git clone:** set `SAAS_BASE_MODULE_REPO` (+ optional `SAAS_BASE_MODULE_REF`).
3. **SCP from server (quickest):** set `SAAS_BASE_SSH_HOST`, `SAAS_BASE_SSH_PATH`,
   and `SAAS_BASE_SSH_KEY`.

Local devs: just run `./scripts/ci_fetch_base_module.sh` (or the one-liner in
`vendor/README.md`).

### Production env protection
Configure GitHub → Settings → Environments → `production` → **Required reviewers**
so the `deploy-production` job pauses for manual approval (the workflow already
targets `environment: production`).

---

**End of Runbook.** For module-specific detail, see each module's `__manifest__.py` description and `tests/`.
