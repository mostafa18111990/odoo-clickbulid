#!/usr/bin/env bash
#
# ci_fetch_base_module.sh — Make `saas_tenant_manager` (the pre-existing base
# module that every saas_* module depends on) available to CI / local tests.
#
# It is NOT part of this repository's source; it is the source of truth on the
# production server. This script obtains it using whichever strategy is
# available, in priority order:
#
#   1. Git submodule         — if .gitmodules defines it (set SAAS_BASE_MODULE_REPO)
#   2. Git clone             — if SAAS_BASE_MODULE_REPO is set
#   3. SCP from server       — if SAAS_BASE_SSH_HOST + key are configured
#   4. Already vendored      — if vendor/saas_tenant_manager already exists
#   5. Fail with guidance
#
# Output: vendor/saas_tenant_manager/
#
# Usage:
#   ./scripts/ci_fetch_base_module.sh
#
# Env vars (all optional; configure at least one source):
#   SAAS_BASE_MODULE_REPO   git URL of the base module repo (or monorepo)
#   SAAS_BASE_MODULE_REF    git ref to checkout (default: main)
#   SAAS_BASE_MODULE_PATH   subdir inside that repo (default: saas_tenant_manager)
#   SAAS_BASE_SSH_HOST      e.g. root@129.121.98.243
#   SAAS_BASE_SSH_PATH      e.g. /opt/odoo-saas/addons/saas_tenant_manager
#   (SSH key must already be loaded into the agent / ~/.ssh)

set -euo pipefail

DEST="vendor/saas_tenant_manager"
REF="${SAAS_BASE_MODULE_REF:-main}"
SUBPATH="${SAAS_BASE_MODULE_PATH:-saas_tenant_manager}"

log() { echo "[fetch-base] $*"; }

# ── 0. Already present? ──────────────────────────────────────────────────────
if [ -f "${DEST}/__manifest__.py" ]; then
  log "✅ Base module already vendored at ${DEST} — nothing to do."
  exit 0
fi

mkdir -p vendor

# ── 1. Git submodule ─────────────────────────────────────────────────────────
if [ -f .gitmodules ] && grep -q "saas_tenant_manager" .gitmodules 2>/dev/null; then
  log "Found submodule definition — initializing…"
  git submodule update --init --recursive
  if [ -f "${DEST}/__manifest__.py" ]; then
    log "✅ Base module obtained via submodule."
    exit 0
  fi
fi

# ── 2. Git clone from configured repo ────────────────────────────────────────
if [ -n "${SAAS_BASE_MODULE_REPO:-}" ]; then
  log "Cloning base module from ${SAAS_BASE_MODULE_REPO} (ref ${REF})…"
  tmp="$(mktemp -d)"
  git clone --depth 1 --branch "${REF}" "${SAAS_BASE_MODULE_REPO}" "${tmp}" 2>/dev/null \
    || git clone --depth 1 "${SAAS_BASE_MODULE_REPO}" "${tmp}"
  if [ -d "${tmp}/${SUBPATH}" ]; then
    cp -r "${tmp}/${SUBPATH}" "${DEST}"
  elif [ -f "${tmp}/__manifest__.py" ]; then
    cp -r "${tmp}" "${DEST}"
  fi
  rm -rf "${tmp}"
  if [ -f "${DEST}/__manifest__.py" ]; then
    log "✅ Base module obtained via git clone."
    exit 0
  fi
fi

# ── 3. SCP from server (source of truth) ─────────────────────────────────────
if [ -n "${SAAS_BASE_SSH_HOST:-}" ]; then
  SSH_PATH="${SAAS_BASE_SSH_PATH:-/opt/odoo-saas/addons/saas_tenant_manager}"
  log "Fetching base module via SCP from ${SAAS_BASE_SSH_HOST}:${SSH_PATH}…"
  scp -r -o StrictHostKeyChecking=no \
    "${SAAS_BASE_SSH_HOST}:${SSH_PATH}" "${DEST}"
  if [ -f "${DEST}/__manifest__.py" ]; then
    log "✅ Base module obtained via SCP."
    exit 0
  fi
fi

# ── 4. Fail with guidance ────────────────────────────────────────────────────
cat >&2 <<EOF
[fetch-base] ❌ Could not obtain saas_tenant_manager.

Configure ONE of the following, then re-run:

  A) Git submodule (recommended once the base module is in its own repo):
       git submodule add <repo-url> vendor/saas_tenant_manager
       git commit -m "Add saas_tenant_manager submodule"

  B) Git clone (CI secret):
       export SAAS_BASE_MODULE_REPO="git@github.com:org/saas_tenant_manager.git"
       export SAAS_BASE_MODULE_REF="main"

  C) SCP from the server (CI secret + SSH key):
       export SAAS_BASE_SSH_HOST="root@129.121.98.243"
       export SAAS_BASE_SSH_PATH="/opt/odoo-saas/addons/saas_tenant_manager"

  D) Vendor it manually (one-time):
       scp -r root@129.121.98.243:/opt/odoo-saas/addons/saas_tenant_manager vendor/
EOF
exit 1
