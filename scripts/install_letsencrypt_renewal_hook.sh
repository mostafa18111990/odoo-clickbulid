#!/bin/bash
# Installs a Let's Encrypt deploy-hook that reloads nginx container after
# every successful certificate renewal. Idempotent — safe to re-run.
set -e
HOOK_DIR=/etc/letsencrypt/renewal-hooks/deploy
HOOK_PATH=$HOOK_DIR/reload-nginx.sh
mkdir -p "$HOOK_DIR"
cat > "$HOOK_PATH" << 'HOOK'
#!/bin/bash
# Reload nginx in the docker container so it picks up the new cert.
# Triggered by certbot after each successful renewal (RENEWED_LINEAGE set).
LOG=/var/log/letsencrypt/deploy-hook.log
{
    echo "=== $(date -Is) === renewed: $RENEWED_LINEAGE"
    if docker ps --format '{{.Names}}' | grep -q '^odoo_saas_nginx$'; then
        docker exec odoo_saas_nginx nginx -t \
            && docker exec odoo_saas_nginx nginx -s reload \
            && echo "OK reloaded odoo_saas_nginx" \
            || echo "FAIL reload (config test failed)"
    else
        echo "FAIL container odoo_saas_nginx not running"
    fi
} >> "$LOG" 2>&1
HOOK
chmod +x "$HOOK_PATH"
echo "[install_renewal_hook] installed $HOOK_PATH"
ls -la "$HOOK_PATH"
