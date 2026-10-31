#!/usr/bin/env bash
# Rehearse or perform a verified rotation of the active Odoo 19/20 credentials.
set -Eeuo pipefail
umask 077

mode=${1:-}
run_id=${2:-manual}

fail() { printf 'FAIL: %s\n' "$*" >&2; return 1; }
random_secret() { openssl rand -hex 32; }

container_env() {
    local container=$1 key=$2
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container" \
        | sed -n "s/^${key}=//p" | head -n 1
}

config_value() {
    local file=$1 key=$2
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$file" | head -n 1
}

alter_role_password() {
    local container=$1 password=$2 escaped
    escaped=${password//\'/\'\'}
    printf "ALTER ROLE odoo PASSWORD '%s';\n" "$escaped" \
        | docker exec -i "$container" psql -v ON_ERROR_STOP=1 -U odoo -d postgres >/dev/null
}

rehearsal_db_auth_works() {
    local network=$1 host=$2 password=$3
    printf '%s\n' "$password" \
        | docker run --rm -i --network "$network" postgres:16-alpine sh -ceu '
            IFS= read -r PGPASSWORD
            export PGPASSWORD
            psql -h "$1" -U odoo -d postgres -Atc "select 1" 2>/dev/null
        ' sh "$host" | grep -qx 1
}

container_db_auth_works() {
    local container=$1 host_key=$2 port_key=$3 password=$4
    printf '%s\n' "$password" \
        | docker exec -i "$container" python3 -c '
import os
import sys
import psycopg2

password = sys.stdin.readline().rstrip("\n")
connection = psycopg2.connect(
    host=os.environ[sys.argv[1]],
    port=os.environ.get(sys.argv[2], "5432"),
    user=os.environ.get("DB_USER") or os.environ.get("USER"),
    password=password,
    dbname="postgres",
)
connection.close()
' "$host_key" "$port_key" >/dev/null 2>&1
}

odoo_http_works() {
    local container=$1
    docker exec "$container" python3 -c '
import http.client

connection = http.client.HTTPConnection("127.0.0.1", 8069, timeout=20)
connection.request("GET", "/web/login")
response = connection.getresponse()
response.read(1024)
if not 200 <= response.status < 400:
    raise SystemExit(1)
' >/dev/null
}

replace_literal() {
    local file=$1 old_value=$2 new_value=$3
    ROTATE_FILE="$file" ROTATE_OLD="$old_value" ROTATE_NEW="$new_value" python3 <<'PY'
import os
from pathlib import Path
import stat
import tempfile

path = Path(os.environ["ROTATE_FILE"])
old = os.environ["ROTATE_OLD"]
new = os.environ["ROTATE_NEW"]
content = path.read_text(encoding="utf-8")
if old not in content:
    raise SystemExit(f"credential value not found in {path}")
updated = content.replace(old, new)
mode = stat.S_IMODE(path.stat().st_mode)
fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

set_env_key() {
    local file=$1 key=$2 value=$3
    ROTATE_FILE="$file" ROTATE_KEY="$key" ROTATE_VALUE="$value" python3 <<'PY'
import os
from pathlib import Path
import stat
import tempfile

path = Path(os.environ["ROTATE_FILE"])
key = os.environ["ROTATE_KEY"]
value = os.environ["ROTATE_VALUE"]
lines = path.read_text(encoding="utf-8").splitlines()
matches = [index for index, line in enumerate(lines) if line.startswith(f"{key}=")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one {key}= entry in {path}")
lines[matches[0]] = f"{key}={value}"
mode = stat.S_IMODE(path.stat().st_mode)
fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

wait_running() {
    local deadline container state
    for container in "$@"; do
        deadline=$((SECONDS + 180))
        state=missing
        while (( SECONDS < deadline )); do
            if ! state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null); then
                state=missing
            fi
            case "$state" in
                running|healthy) break ;;
                unhealthy|exited|dead) fail "$container failed with state=$state" ;;
            esac
            sleep 3
        done
        [[ "$state" == running || "$state" == healthy ]] || fail "$container did not become ready"
    done
}

recreate_odoo19_cron() {
    local compose_file=$1
    docker rm -f odoo_saas_cron odoo_saas_ent_cron >/dev/null
    docker compose -p odoo-saas -f "$compose_file" run -d \
        --name odoo_saas_cron --no-deps odoo \
        odoo -c /etc/odoo/odoo.conf --no-http --workers=0 --max-cron-threads=1 --db_maxconn=8 \
        >/dev/null
    docker compose -p odoo-saas -f "$compose_file" run -d \
        --name odoo_saas_ent_cron --no-deps odoo_ent \
        odoo -c /etc/odoo/odoo.conf --no-http --workers=0 --max-cron-threads=1 --db_maxconn=8 \
        >/dev/null
}

cron_shape_matches() {
    local container=$1 expected_service=$2
    docker inspect "$container" | python3 -c '
import json
import sys

item = json.load(sys.stdin)[0]
config = item.get("Config") or {}
labels = config.get("Labels") or {}
expected = [
    "odoo", "-c", "/etc/odoo/odoo.conf", "--no-http", "--workers=0",
    "--max-cron-threads=1", "--db_maxconn=8",
]
valid = (
    config.get("Entrypoint") == ["/entrypoint.sh"]
    and config.get("Cmd") == expected
    and labels.get("com.docker.compose.project") == "odoo-saas"
    and labels.get("com.docker.compose.service") == sys.argv[1]
    and labels.get("com.docker.compose.oneoff") == "True"
)
raise SystemExit(0 if valid else 1)
' "$expected_service"
}

rehearse() {
    [[ "$(id -u)" == 0 ]] || fail 'rehearsal must run as root'
    [[ "$run_id" =~ ^[0-9]{1,20}$ ]] || fail 'invalid rehearsal run id'
    local root network pg19 pg20 old19 old20 new19 new20
    root=$(mktemp -d "/run/clickbuild-credential-rehearsal-${run_id}.XXXXXX")
    network="cb_cred_net_${run_id}"
    pg19="cb_cred_pg15_${run_id}"
    pg20="cb_cred_pg16_${run_id}"
    old19=$(random_secret); old20=$(random_secret)
    new19=$(random_secret); new20=$(random_secret)
    cleanup_rehearsal() {
        docker rm -f "$pg19" "$pg20" >/dev/null 2>&1 || :
        docker network rm "$network" >/dev/null 2>&1 || :
        [[ "$root" == /run/clickbuild-credential-rehearsal-* ]] && rm -rf -- "$root"
    }
    trap cleanup_rehearsal EXIT

    printf 'POSTGRES_USER=odoo\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD=%s\n' "$old19" >"$root/pg15.env"
    printf 'POSTGRES_USER=odoo\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD=%s\n' "$old20" >"$root/pg16.env"
    docker network create "$network" >/dev/null
    docker run -d --rm --name "$pg19" --network "$network" --env-file "$root/pg15.env" postgres:15-alpine >/dev/null
    docker run -d --rm --name "$pg20" --network "$network" --env-file "$root/pg16.env" postgres:16-alpine >/dev/null
    for _ in $(seq 1 60); do
        docker exec "$pg19" pg_isready -U odoo -d postgres >/dev/null 2>&1 \
            && docker exec "$pg20" pg_isready -U odoo -d postgres >/dev/null 2>&1 \
            && break
        sleep 2
    done
    rehearsal_db_auth_works "$network" "$pg19" "$old19" || fail 'PostgreSQL 15 rehearsal did not start'
    rehearsal_db_auth_works "$network" "$pg20" "$old20" || fail 'PostgreSQL 16 rehearsal did not start'

    printf 'db_password = %s\nadmin_passwd = old-master-19\n' "$old19" >"$root/odoo19.conf"
    printf 'ODOO20_DB_PASSWORD=%s\nODOO20_MASTER_PASSWORD=old-master-20\n' "$old20" >"$root/odoo20.env"
    cp -a "$root/odoo19.conf" "$root/odoo19.conf.before"
    cp -a "$root/odoo20.env" "$root/odoo20.env.before"

    replace_literal "$root/odoo19.conf" "$old19" "$new19"
    replace_literal "$root/odoo19.conf" old-master-19 new-master-19
    set_env_key "$root/odoo20.env" ODOO20_DB_PASSWORD "$new20"
    set_env_key "$root/odoo20.env" ODOO20_MASTER_PASSWORD new-master-20
    alter_role_password "$pg19" "$new19"
    alter_role_password "$pg20" "$new20"
    rehearsal_db_auth_works "$network" "$pg19" "$new19" || fail 'PostgreSQL 15 new password failed'
    rehearsal_db_auth_works "$network" "$pg20" "$new20" || fail 'PostgreSQL 16 new password failed'
    if rehearsal_db_auth_works "$network" "$pg19" "$old19" \
        || rehearsal_db_auth_works "$network" "$pg20" "$old20"; then
        fail 'an old rehearsal password still works'
    fi

    # Rehearse rollback and prove both old passwords work again.
    cp -a "$root/odoo19.conf.before" "$root/odoo19.conf"
    cp -a "$root/odoo20.env.before" "$root/odoo20.env"
    alter_role_password "$pg19" "$old19"
    alter_role_password "$pg20" "$old20"
    rehearsal_db_auth_works "$network" "$pg19" "$old19" || fail 'PostgreSQL 15 rollback verification failed'
    rehearsal_db_auth_works "$network" "$pg20" "$old20" || fail 'PostgreSQL 16 rollback verification failed'
    if rehearsal_db_auth_works "$network" "$pg19" "$new19" \
        || rehearsal_db_auth_works "$network" "$pg20" "$new20"; then
        fail 'a rehearsal password remained valid after rollback'
    fi
    echo 'CREDENTIAL_ROTATION_REHEARSAL_OK postgres15=yes postgres16=yes rollback=yes'
}

production() {
    [[ "$(id -u)" == 0 ]] || fail 'production rotation must run as root'
    [[ "$run_id" =~ ^[0-9]{1,20}$ ]] || fail 'invalid production run id'
    local pg19=odoo_saas_postgres pg20=odoo_saas_postgres20
    local app19=odoo_saas_app ent19=odoo_saas_ent
    local cron19=odoo_saas_cron cron19_ent=odoo_saas_ent_cron
    local app20=odoo_saas_20_community ent20=odoo_saas_20_enterprise
    local compose19=/opt/odoo-saas/docker-compose.yml
    local conf19=/opt/odoo-saas/config/odoo.conf
    local conf19_ent=/opt/odoo-saas/docker-enterprise/odoo-enterprise.conf
    local env20_source=/opt/odoo20-staging/repo/docker/odoo20/.env
    local release20 compose20 env20_current
    release20=$(readlink -f /opt/odoo20-releases/current)
    compose20="$release20/docker/odoo20/docker-compose.tenants.yml"
    env20_current="$release20/docker/odoo20/.env"
    local required=("$compose19" "$conf19" "$conf19_ent" "$env20_source" "$compose20" "$env20_current")
    local file
    for file in "${required[@]}"; do [[ -f "$file" ]] || fail "missing runtime file: $file"; done
    for file in "$pg19" "$app19" "$ent19" "$cron19" "$cron19_ent" "$pg20" "$app20" "$ent20"; do
        docker inspect "$file" >/dev/null 2>&1 || fail "missing container: $file"
    done
    cron_shape_matches "$cron19" odoo || fail 'unexpected Odoo 19 Community cron shape'
    cron_shape_matches "$cron19_ent" odoo_ent || fail 'unexpected Odoo 19 Enterprise cron shape'

    exec 9>/run/lock/clickbuild-credential-rotation.lock
    flock -n 9 || fail 'another credential rotation is already running'

    local old_db19 old_db20 old_master19 old_master19_ent old_master20
    old_db19=$(container_env "$pg19" POSTGRES_PASSWORD)
    old_db20=$(container_env "$pg20" POSTGRES_PASSWORD)
    old_master19=$(config_value "$conf19" admin_passwd)
    old_master19_ent=$(config_value "$conf19_ent" admin_passwd)
    old_master20=$(container_env "$app20" MASTER_PASSWORD)
    [[ -n "$old_db19" && -n "$old_db20" && -n "$old_master19" && -n "$old_master19_ent" && -n "$old_master20" ]] \
        || fail 'could not read all current credentials'
    [[ "$(container_env "$app19" PASSWORD)" == "$old_db19" ]] || fail 'Odoo 19 Community DB credential mismatch'
    [[ "$(container_env "$ent19" PASSWORD)" == "$old_db19" ]] || fail 'Odoo 19 Enterprise DB credential mismatch'
    [[ "$(container_env "$cron19" PASSWORD)" == "$old_db19" ]] || fail 'Odoo 19 Community cron DB credential mismatch'
    [[ "$(container_env "$cron19_ent" PASSWORD)" == "$old_db19" ]] || fail 'Odoo 19 Enterprise cron DB credential mismatch'
    [[ "$(container_env "$app20" DB_PASSWORD)" == "$old_db20" ]] || fail 'Odoo 20 Community DB credential mismatch'
    [[ "$(container_env "$ent20" DB_PASSWORD)" == "$old_db20" ]] || fail 'Odoo 20 Enterprise DB credential mismatch'
    [[ "$(container_env "$ent20" MASTER_PASSWORD)" == "$old_master20" ]] || fail 'Odoo 20 master credential mismatch'
    docker compose -p odoo-saas -f "$compose19" config --quiet
    ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20 \
        docker compose -p clickbuild-odoo20-tenants -f "$compose20" --env-file "$env20_current" config --quiet
    container_db_auth_works "$app19" HOST PORT "$old_db19" \
        || fail 'current Odoo 19 database password failed preflight'
    container_db_auth_works "$app20" DB_HOST DB_PORT "$old_db20" \
        || fail 'current Odoo 20 database password failed preflight'
    odoo_http_works "$app19" || fail 'Odoo 19 Community HTTP preflight failed'
    odoo_http_works "$ent19" || fail 'Odoo 19 Enterprise HTTP preflight failed'
    odoo_http_works "$app20" || fail 'Odoo 20 Community HTTP preflight failed'
    odoo_http_works "$ent20" || fail 'Odoo 20 Enterprise HTTP preflight failed'
    curl -fsS --max-time 30 https://odoo.clickbulid.com/web/login >/dev/null \
        || fail 'public Odoo route preflight failed'

    local new_db19 new_db20 new_master19 new_master19_ent new_master20
    new_db19=$(random_secret); new_db20=$(random_secret)
    new_master19=$(random_secret); new_master19_ent=$(random_secret); new_master20=$(random_secret)
    local stamp snapshot full_backup backup_day
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    snapshot="/opt/backups/pre-credential-rotation-$stamp"
    install -d -o root -g root -m 700 "$snapshot/files" "$snapshot/full"

    snapshot_name() { printf '%s' "$1" | sed 's#^/##; s#/#__#g'; }
    for file in "${required[@]}"; do cp -a "$file" "$snapshot/files/$(snapshot_name "$file")"; done
    (
        cd "$snapshot/files"
        find . -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
        sha256sum -c SHA256SUMS >/dev/null
    )

    local backup_script=${SAAS_BACKUP_SCRIPT:-/usr/local/bin/saas-backup-all.sh}
    [[ -x "$backup_script" ]] || fail 'verified backup script is unavailable'
    BACKUP_ROOT="$snapshot/full" SAAS_BACKUP_LOG="$snapshot/backup.log" \
        SAAS_BACKUP_SKIP_OFFSITE=1 "$backup_script"
    backup_day="$snapshot/full/$(date +%Y-%m-%d)"
    [[ -s "$backup_day/MANIFEST.txt" && -s "$backup_day/SHA256SUMS" ]] || fail 'verified backup manifest is missing'
    (cd "$backup_day" && sha256sum -c SHA256SUMS >/dev/null)

    local mutation_started=0
    rollback() {
        local rc=$?
        trap - ERR
        set +e
        if [[ "$mutation_started" == 1 ]]; then
            echo "ROLLBACK: restoring credential files and database roles from $snapshot" >&2
            local restore_rc=0 name
            for file in "${required[@]}"; do
                name=$(snapshot_name "$file")
                cp -a "$snapshot/files/$name" "$file" || restore_rc=1
            done
            docker compose -p odoo-saas -f "$compose19" up -d --force-recreate postgres || restore_rc=1
            ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20 \
                docker compose -p clickbuild-odoo20-tenants -f "$compose20" --env-file "$env20_current" \
                    up -d --force-recreate postgres20 || restore_rc=1
            wait_running "$pg19" "$pg20" || restore_rc=1
            alter_role_password "$pg19" "$old_db19" || restore_rc=1
            alter_role_password "$pg20" "$old_db20" || restore_rc=1
            docker compose -p odoo-saas -f "$compose19" up -d --force-recreate odoo odoo_ent || restore_rc=1
            recreate_odoo19_cron "$compose19" || restore_rc=1
            ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20 \
                docker compose -p clickbuild-odoo20-tenants -f "$compose20" --env-file "$env20_current" \
                    up -d --force-recreate odoo20-community odoo20-enterprise || restore_rc=1
            wait_running "$pg19" "$app19" "$ent19" "$cron19" "$cron19_ent" "$pg20" "$app20" "$ent20" || restore_rc=1
            container_db_auth_works "$app19" HOST PORT "$old_db19" || restore_rc=1
            container_db_auth_works "$app20" DB_HOST DB_PORT "$old_db20" || restore_rc=1
            if container_db_auth_works "$app19" HOST PORT "$new_db19" \
                || container_db_auth_works "$app20" DB_HOST DB_PORT "$new_db20"; then
                restore_rc=1
            fi
            [[ "$(container_env "$app19" PASSWORD)" == "$old_db19" ]] || restore_rc=1
            [[ "$(container_env "$ent19" PASSWORD)" == "$old_db19" ]] || restore_rc=1
            [[ "$(container_env "$cron19" PASSWORD)" == "$old_db19" ]] || restore_rc=1
            [[ "$(container_env "$cron19_ent" PASSWORD)" == "$old_db19" ]] || restore_rc=1
            [[ "$(container_env "$app20" DB_PASSWORD)" == "$old_db20" ]] || restore_rc=1
            [[ "$(container_env "$ent20" DB_PASSWORD)" == "$old_db20" ]] || restore_rc=1
            odoo_http_works "$app19" || restore_rc=1
            odoo_http_works "$ent19" || restore_rc=1
            odoo_http_works "$app20" || restore_rc=1
            odoo_http_works "$ent20" || restore_rc=1
            curl -fsS --max-time 30 https://odoo.clickbulid.com/web/login >/dev/null || restore_rc=1
            [[ "$restore_rc" == 0 ]] || echo 'ROLLBACK_INCOMPLETE' >&2
        fi
        exit "$rc"
    }
    trap rollback ERR
    mutation_started=1

    replace_literal "$compose19" "$old_db19" "$new_db19"
    replace_literal "$conf19" "$old_db19" "$new_db19"
    replace_literal "$conf19" "$old_master19" "$new_master19"
    replace_literal "$conf19_ent" "$old_db19" "$new_db19"
    replace_literal "$conf19_ent" "$old_master19_ent" "$new_master19_ent"
    for file in "$env20_source" "$env20_current"; do
        set_env_key "$file" ODOO20_DB_PASSWORD "$new_db20"
        set_env_key "$file" ODOO20_MASTER_PASSWORD "$new_master20"
    done

    docker compose -p odoo-saas -f "$compose19" config --quiet
    ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20 \
        docker compose -p clickbuild-odoo20-tenants -f "$compose20" --env-file "$env20_current" config --quiet

    alter_role_password "$pg19" "$new_db19"
    alter_role_password "$pg20" "$new_db20"
    docker compose -p odoo-saas -f "$compose19" up -d --force-recreate postgres odoo odoo_ent
    recreate_odoo19_cron "$compose19"
    ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20 \
        docker compose -p clickbuild-odoo20-tenants -f "$compose20" --env-file "$env20_current" \
            up -d --force-recreate postgres20 odoo20-community odoo20-enterprise
    wait_running "$pg19" "$app19" "$ent19" "$cron19" "$cron19_ent" "$pg20" "$app20" "$ent20"

    container_db_auth_works "$app19" HOST PORT "$new_db19" || fail 'new Odoo 19 database password failed'
    container_db_auth_works "$app20" DB_HOST DB_PORT "$new_db20" || fail 'new Odoo 20 database password failed'
    if container_db_auth_works "$app19" HOST PORT "$old_db19" \
        || container_db_auth_works "$app20" DB_HOST DB_PORT "$old_db20"; then
        fail 'an old database password remains valid'
    fi
    [[ "$(container_env "$app19" PASSWORD)" == "$new_db19" ]] || fail 'Odoo 19 Community did not receive new credential'
    [[ "$(container_env "$ent19" PASSWORD)" == "$new_db19" ]] || fail 'Odoo 19 Enterprise did not receive new credential'
    [[ "$(container_env "$cron19" PASSWORD)" == "$new_db19" ]] || fail 'Odoo 19 Community cron did not receive new credential'
    [[ "$(container_env "$cron19_ent" PASSWORD)" == "$new_db19" ]] || fail 'Odoo 19 Enterprise cron did not receive new credential'
    [[ "$(container_env "$app20" DB_PASSWORD)" == "$new_db20" ]] || fail 'Odoo 20 Community did not receive new credential'
    [[ "$(container_env "$ent20" DB_PASSWORD)" == "$new_db20" ]] || fail 'Odoo 20 Enterprise did not receive new credential'
    [[ "$(container_env "$app20" MASTER_PASSWORD)" == "$new_master20" ]] || fail 'Odoo 20 master credential was not updated'
    [[ "$(config_value "$conf19" admin_passwd)" == "$new_master19" ]] || fail 'Odoo 19 Community master credential was not updated'
    [[ "$(config_value "$conf19_ent" admin_passwd)" == "$new_master19_ent" ]] || fail 'Odoo 19 Enterprise master credential was not updated'

    docker exec "$app19" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["HOST"], port=os.environ.get("PORT", "5432"), user=os.environ["USER"], password=os.environ["PASSWORD"], dbname="postgres").close()'
    docker exec "$ent19" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["HOST"], port=os.environ.get("PORT", "5432"), user=os.environ["USER"], password=os.environ["PASSWORD"], dbname="postgres").close()'
    docker exec "$cron19" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["HOST"], port=os.environ.get("PORT", "5432"), user=os.environ["USER"], password=os.environ["PASSWORD"], dbname="postgres").close()'
    docker exec "$cron19_ent" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["HOST"], port=os.environ.get("PORT", "5432"), user=os.environ["USER"], password=os.environ["PASSWORD"], dbname="postgres").close()'
    docker exec "$app20" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dbname="postgres").close()'
    docker exec "$ent20" python3 -c 'import os, psycopg2; psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dbname="postgres").close()'
    odoo_http_works "$app19"
    odoo_http_works "$ent19"
    odoo_http_works "$app20"
    odoo_http_works "$ent20"
    curl -fsS --max-time 30 https://odoo.clickbulid.com/web/login >/dev/null

    trap - ERR
    mutation_started=0
    echo "CREDENTIAL_ROTATION_OK snapshot=$snapshot odoo19=yes odoo20=yes old_credentials_rejected=yes"
}

case "$mode" in
    rehearse) rehearse ;;
    production) production ;;
    *) fail 'usage: rotate_odoo_runtime_credentials.sh rehearse|production RUN_ID' ;;
esac
