#!/bin/bash
# Monitor provisioning errors and auto-recover

LOG_DIR="/opt/logs"
MONITOR_LOG="$LOG_DIR/saas-error-monitor.log"
ERROR_THRESHOLD=3
RECOVERY_COOLDOWN=300

# Setup logging
mkdir -p "$LOG_DIR"
exec 1> >(tee -a "$MONITOR_LOG")
exec 2>&1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Check for critical errors in Odoo logs
check_critical_errors() {
    local odoo_log="/opt/odoo-saas/odoo.log"
    local error_count=$(grep -c "ERROR" "$odoo_log" 2>/dev/null | tail -100 || echo 0)

    if [ "$error_count" -gt "$ERROR_THRESHOLD" ]; then
        log "⚠️ Critical errors detected ($error_count). Investigating..."

        # Extract recent errors
        tail -100 "$odoo_log" | grep "ERROR" | tail -5

        # Trigger notification
        notify_admins "Critical errors: $error_count in last 100 lines"
    fi
}

# Check database connectivity
check_db_connectivity() {
    local result=$(docker exec odoo_saas_postgres psql -U odoo -d odoo -c "SELECT 1" 2>&1)

    if [[ ! "$result" == *"1"* ]]; then
        log "❌ Database connectivity failed!"
        notify_admins "Database connection error"
        return 1
    fi

    log "✅ Database connectivity OK"
    return 0
}

# Check provisioning queue
check_provisioning_queue() {
    local stuck_count=$(docker exec odoo_saas_app python3 /opt/odoo-saas/manage.py check_stuck_provisions 2>/dev/null || echo 0)

    if [ "$stuck_count" -gt 0 ]; then
        log "⚠️ Found $stuck_count stuck provision requests"

        # Attempt recovery
        for i in {1..3}; do
            log "Recovery attempt $i/3..."
            docker exec odoo_saas_app python3 /opt/odoo-saas/manage.py retry_stuck_provisions
            sleep 10
        done
    fi
}

# Check certificate health
check_certificates() {
    local expired=$(certbot certificates 2>&1 | grep -c "EXPIRED" || echo 0)

    if [ "$expired" -gt 0 ]; then
        log "❌ Found $expired expired certificates!"
        notify_admins "Expired SSL certificates: $expired"

        # Auto-renew
        certbot renew --quiet
        docker exec odoo_saas_nginx nginx -s reload
    fi
}

# Monitor disk space
check_disk_space() {
    local used=$(df /opt | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$used" -gt 80 ]; then
        log "⚠️ Disk usage high: ${used}%"
        notify_admins "Disk space warning: ${used}% used"
    fi
}

# Monitor container health
check_container_health() {
    for container in odoo_saas_app odoo_saas_ent odoo_saas_postgres odoo_saas_nginx; do
        local status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)

        if [ "$status" != "running" ]; then
            log "❌ Container $container is $status"
            notify_admins "Container failure: $container is $status"

            # Auto-restart
            docker start "$container" 2>/dev/null
        fi
    done
}

# Send notifications
notify_admins() {
    local message="$1"

    # Log to database via Odoo API
    curl -s -X POST http://localhost:8069/health \
        -H "Content-Type: application/json" \
        -d "{\"error\": \"$message\", \"severity\": \"critical\"}" \
        2>/dev/null || true

    # Send email if configured
    # sendmail -t <<< "To: admin@clickbuild.com\nSubject: ⚠️ Platform Alert\n\n$message"
}

# Main monitoring loop
main() {
    log "=== Platform Error Monitor Started ==="

    while true; do
        log "Running health checks..."

        check_db_connectivity || true
        check_critical_errors || true
        check_provisioning_queue || true
        check_certificates || true
        check_disk_space || true
        check_container_health || true

        log "Health checks completed. Sleeping for 5 minutes..."
        sleep 300
    done
}

# Handle signals
trap "log 'Monitor stopped'; exit 0" SIGTERM SIGINT

# Run
main
