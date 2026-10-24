#!/bin/bash
# Root-only staging smoke test for curated Odoo 20 sector bundles.
set -Eeuo pipefail
umask 077

RUN_ID=${1:-}
[[ "$RUN_ID" =~ ^[0-9]{1,20}$ ]] || {
    echo 'FAIL: numeric GitHub run id required' >&2
    exit 2
}

DB_CONTAINER=odoo_saas_postgres20
PREFIX="cbsector${RUN_ID}"
DATABASES=(
    "${PREFIX}restaurant"
    "${PREFIX}manufacturing"
    "${PREFIX}manufacturingee"
    "${PREFIX}servicesee"
)

cleanup() {
    local database
    for database in "${DATABASES[@]}"; do
        docker exec "$DB_CONTAINER" dropdb -U odoo --if-exists --force "$database"
    done
}
trap cleanup EXIT

container_healthy() {
    local state
    state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1")
    [ "$state" = healthy ] || [ "$state" = running ] || {
        echo "FAIL: $1 is not healthy (state=$state)" >&2
        exit 3
    }
}

smoke_bundle() {
    local container=$1 database=$2 modules=$3 module state
    docker exec "$DB_CONTAINER" createdb -U odoo -O odoo "$database"
    docker exec "$container" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$database" -i "$modules" \
        --without-demo --load-language=ar_001 \
        --no-http --stop-after-init
    IFS=',' read -ra required_modules <<< "$modules"
    for module in "${required_modules[@]}"; do
        state=$(docker exec "$DB_CONTAINER" psql -U odoo -d "$database" -Atc \
            "select state from ir_module_module where name='$module'")
        [ "$state" = installed ] || {
            echo "FAIL: $module was not installed in $database (state=${state:-missing})" >&2
            exit 4
        }
    done
}

for container in "$DB_CONTAINER" odoo_saas_20_community odoo_saas_20_enterprise; do
    container_healthy "$container"
done
docker exec odoo_saas_20_community odoo --version | grep -q 'Odoo Server 20'
docker exec odoo_saas_20_enterprise odoo --version | grep -q 'Odoo Server 20'

smoke_bundle odoo_saas_20_community "${DATABASES[0]}" \
    'base,web,point_of_sale,pos_restaurant,purchase,stock,account'
smoke_bundle odoo_saas_20_community "${DATABASES[1]}" \
    'base,web,mrp,stock,purchase,sale_management,maintenance,account'
smoke_bundle odoo_saas_20_enterprise "${DATABASES[2]}" \
    'base,web,mrp,stock,purchase,sale_management,maintenance,account,quality'
smoke_bundle odoo_saas_20_enterprise "${DATABASES[3]}" \
    'base,web,project,sale_management,hr_timesheet,account,helpdesk,planning'

echo 'PASS: Odoo 20 sector bundles installed successfully in disposable staging databases.'
