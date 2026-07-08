#!/bin/bash
# Maintain a warm pool of pre-cloned tenant databases so a signup can grab a
# ready DB instantly (a rename) instead of cloning the template on the
# critical path. Pool DBs are named pool_<hex> and OWNED BY the `odoo` role
# so the community Odoo server (connecting as odoo_community) never lists or
# serves them — no connections, safe to rename on grab.
#
# Run by a systemd timer + kicked after each grab to top back up.
set -uo pipefail

POOL_SIZE="${SAAS_POOL_SIZE:-3}"
TEMPLATE_DB=tpl_community_core
PG=odoo_saas_postgres
ODOO=odoo_saas_app
LOG=/var/log/saas-warm-pool.log

log() { echo "$(date -Is) $*" >> "$LOG"; }

template_exists() {
    docker exec "$PG" psql -U odoo -lqt 2>/dev/null \
        | cut -d'|' -f1 | tr -d ' ' | grep -qx "$TEMPLATE_DB"
}
template_exists || { log "template $TEMPLATE_DB missing — pool disabled"; exit 0; }

current_pool() {
    docker exec "$PG" psql -U odoo -tAc \
        "select count(*) from pg_database where datname like 'pool\_%'" 2>/dev/null | tr -d ' '
}

have=$(current_pool); have=${have:-0}
log "pool maintenance: have=$have target=$POOL_SIZE"

while [ "${have:-0}" -lt "$POOL_SIZE" ]; do
    name="pool_$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    # Clone template (owned by odoo → invisible to odoo_community) + filestore.
    if docker exec "$PG" createdb -U odoo -T "$TEMPLATE_DB" -O odoo "$name" >> "$LOG" 2>&1; then
        docker exec "$ODOO" sh -c \
            "rm -rf /var/lib/odoo/filestore/$name && cp -a /var/lib/odoo/filestore/$TEMPLATE_DB /var/lib/odoo/filestore/$name" >> "$LOG" 2>&1 || true
        log "created pool db $name"
    else
        log "FAILED to create pool db $name — aborting this run"
        break
    fi
    have=$((have + 1))
done

log "pool maintenance done: have=$(current_pool)"
