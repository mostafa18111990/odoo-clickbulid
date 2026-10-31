#!/usr/bin/env bash
# Read-only inventory for planning production credential rotation.
set -Eeuo pipefail

expected_user=${EXPECTED_EFFECTIVE_USER:-github-runner}
[[ "$(id -un)" == "$expected_user" ]] || {
    echo "FAIL: expected effective user $expected_user" >&2
    exit 10
}

command -v docker >/dev/null
docker info >/dev/null

seed_containers=(
    odoo_saas_postgres
    odoo_saas_app
    odoo_saas_odoo
    odoo_saas_ent
    odoo_saas_nginx
    odoo_saas_postgres20
    odoo_saas_20_community
    odoo_saas_20_enterprise
    clickbuild_postgres
    clickbuild_backend
)

declare -A seen=()
containers=()
add_container() {
    local name=${1:-}
    [[ -n "$name" ]] || return 0
    [[ -z "${seen[$name]:-}" ]] || return 0
    seen[$name]=1
    containers+=("$name")
}
for container in "${seed_containers[@]}"; do
    add_container "$container"
done
while IFS= read -r container; do
    add_container "$container"
done < <(docker ps -a \
    --filter label=com.docker.compose.project=odoo-saas \
    --format '{{.Names}}' | LC_ALL=C sort)
while IFS= read -r container; do
    add_container "$container"
done < <(docker ps -a \
    --filter label=com.docker.compose.project=clickbuild-odoo20-tenants \
    --format '{{.Names}}' | LC_ALL=C sort)

printf 'RUNTIME_CREDENTIAL_TOPOLOGY_BEGIN\n'
printf 'runner_user=%s\n' "$(id -un)"
printf 'host=%s\n' "$(hostname)"

found=0
for container in "${containers[@]}"; do
    if ! docker inspect "$container" >/dev/null 2>&1; then
        continue
    fi
    found=$((found + 1))
    status=$(docker inspect --format '{{.State.Status}}' "$container")
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")
    image=$(docker inspect --format '{{.Config.Image}}' "$container")
    project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$container")
    service=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$container")
    working_dir=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$container")
    config_files=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$container")

    printf 'container=%s status=%s health=%s image=%s\n' \
        "$container" "$status" "$health" "$image"
    printf 'compose container=%s project=%s service=%s working_dir=%s config_files=%s\n' \
        "$container" "${project:-none}" "${service:-none}" \
        "${working_dir:-none}" "${config_files:-none}"

    # Names are useful for planning; values must never enter logs.
    env_names=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container" \
        | sed -n 's/=.*//p' | LC_ALL=C sort -u | paste -sd, -)
    printf 'env_names container=%s names=%s\n' "$container" "${env_names:-none}"

    docker inspect --format '{{range .Mounts}}{{println .Destination "|" .Type "|" .Source}}{{end}}' "$container" \
        | while IFS='|' read -r destination type source; do
            destination=$(printf '%s' "$destination" | xargs)
            type=$(printf '%s' "$type" | xargs)
            source=$(printf '%s' "$source" | xargs)
            case "$destination" in
                /etc/odoo/*|/var/lib/postgresql/data|/mnt/enterprise|/mnt/extra-addons)
                    printf 'mount container=%s destination=%s type=%s source=%s\n' \
                        "$container" "$destination" "$type" "$source"
                    ;;
            esac
        done
done

[[ "$found" -gt 0 ]] || {
    echo 'FAIL: no expected platform containers found' >&2
    exit 11
}

printf 'RUNTIME_CREDENTIAL_TOPOLOGY_END containers=%s\n' "$found"
