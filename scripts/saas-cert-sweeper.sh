#!/bin/bash
# Unified sweeper:
#   *.provision.req → run saas-tenant-provisioner.sh (creates DB + Odoo + cert)
#   *.delete.req    → run saas-tenant-destroyer.sh (verified final backup, then
#                     drop DB, filestore, nginx vhost). Written by saas_core.
#   *.req           → run /opt/odoo-saas/provision_tenant_cert.sh (HTTPS only)
# The path/command variables can be overridden from the environment for tests.
set -e
REQ_DIR="${SAAS_REQ_DIR:-/opt/odoo-saas/cert-requests}"
LOG="${SAAS_SWEEPER_LOG:-/var/log/saas-cert-sweeper.log}"
PROVISIONER="${SAAS_PROVISIONER:-/usr/local/bin/saas-tenant-provisioner.sh}"
DESTROYER="${SAAS_DESTROYER:-/usr/local/bin/saas-tenant-destroyer.sh}"
PYTHON="${SAAS_PYTHON:-python3}"
CERT_SCRIPT="${SAAS_CERT_SCRIPT:-/opt/odoo-saas/provision_tenant_cert.sh}"
# Platform databases a delete request must never touch.
RESERVED_RE='^(odoo|postgres|template0|template1|master|saas|saas-master)$'

shopt -s nullglob

# --- Tenant DB provisioning (priority) ---
for req in "$REQ_DIR"/*.provision.req; do
    sub=$(basename "$req" .provision.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping provision $sub" >> "$LOG"
    if bash "$PROVISIONER" "$req" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.provision.done"
        echo "$(date -Is) PROVISION DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.provision.error"
        echo "$(date -Is) PROVISION ERROR $sub" >> "$LOG"
    fi
done

# --- Tenant destruction ---
for req in "$REQ_DIR"/*.delete.req; do
    sub=$(basename "$req" .delete.req)
    clean=$(echo "$sub" | tr -cd 'a-z0-9-')
    if [ -z "$clean" ] || [ "$clean" != "$sub" ] || [[ "$clean" =~ $RESERVED_RE ]]; then
        mv "$req" "$REQ_DIR/$(echo "${sub:-unnamed}" | tr -cd 'a-zA-Z0-9-').delete.error"
        echo "$(date -Is) DELETE REFUSED (invalid or reserved name) $sub" >> "$LOG"
        continue
    fi
    # The request body must name the same tenant as the file.
    body_sub=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("subdomain",""))' "$req" 2>/dev/null || true)
    if [ "$body_sub" != "$sub" ]; then
        mv "$req" "$REQ_DIR/$sub.delete.error"
        echo "$(date -Is) DELETE REFUSED (body subdomain '$body_sub' != '$sub')" >> "$LOG"
        continue
    fi
    echo "$(date -Is) sweeping delete $sub" >> "$LOG"
    if bash "$DESTROYER" "$req" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.delete.done"
        echo "$(date -Is) DELETE DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.delete.error"
        echo "$(date -Is) DELETE ERROR $sub" >> "$LOG"
    fi
done

# --- HTTPS cert provisioning (after DB exists) ---
for req in "$REQ_DIR"/*.req; do
    # Requests handled above must not be treated as cert requests.
    [[ "$req" == *.provision.req || "$req" == *.delete.req ]] && continue
    sub=$(basename "$req" .req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping cert $sub" >> "$LOG"
    if bash "$CERT_SCRIPT" "$sub" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.done"
        echo "$(date -Is) CERT DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.error"
        echo "$(date -Is) CERT ERROR $sub" >> "$LOG"
    fi
done
