#!/bin/bash
# Adds the Enterprise Odoo container to the existing docker-compose stack.
# Idempotent — safe to re-run.
#
# What it does:
#   1. Copies docker/enterprise/{Dockerfile,odoo-enterprise.conf} to /opt/odoo-saas/
#   2. Builds the Enterprise image (using an empty placeholder if no enterprise
#      tree yet — you can rebuild later when you've pulled the real source)
#   3. Adds an `odoo_ent` service to docker-compose.yml
#   4. Wires `/etc/odoo/odoo.conf` to the enterprise config
#   5. Brings the new container up
#
# Sister script: install_enterprise_source.sh (you'll run that once you have
# git access to github.com/odoo/enterprise).
set -euo pipefail
cd /opt/odoo-saas

: "${CLICKBUILD_ODOO_DB_PASSWORD:?CLICKBUILD_ODOO_DB_PASSWORD is required}"
: "${CLICKBUILD_ODOO_MASTER_PASSWORD:?CLICKBUILD_ODOO_MASTER_PASSWORD is required}"

COMPOSE=/opt/odoo-saas/docker-compose.yml

# 1) Stage Dockerfile + config in /opt/odoo-saas/docker-enterprise/
mkdir -p docker-enterprise/empty
cp /tmp/enterprise_Dockerfile             docker-enterprise/Dockerfile
python3 - /tmp/enterprise_odoo.conf docker-enterprise/odoo-enterprise.conf <<'PY'
import os
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding='utf-8')
rendered = (source
            .replace('__CLICKBUILD_ODOO_DB_PASSWORD__',
                     os.environ['CLICKBUILD_ODOO_DB_PASSWORD'])
            .replace('__CLICKBUILD_ODOO_MASTER_PASSWORD__',
                     os.environ['CLICKBUILD_ODOO_MASTER_PASSWORD']))
Path(sys.argv[2]).write_text(rendered, encoding='utf-8')
PY
chmod 600 docker-enterprise/odoo-enterprise.conf
[ -f docker-enterprise/empty/.keep ] || touch docker-enterprise/empty/.keep

# 2) Pick the enterprise source path: real tree if present, else placeholder.
if [ -d /opt/odoo-saas/enterprise ] && [ -f /opt/odoo-saas/enterprise/__init__.py -o -d /opt/odoo-saas/enterprise/website_studio ]; then
    SRC=./enterprise
    echo "[install] using REAL enterprise tree at /opt/odoo-saas/enterprise"
else
    SRC=./docker-enterprise/empty
    echo "[install] enterprise tree not found, building with EMPTY placeholder"
    echo "[install]   → image will start but no Studio/Helpdesk/etc. until you re-build"
fi

# 3) Build the image.
echo "[install] building clickbuild/odoo-enterprise:19 ..."
docker build \
    -f docker-enterprise/Dockerfile \
    -t clickbuild/odoo-enterprise:19 \
    --build-arg ENTERPRISE_SRC=$SRC \
    /opt/odoo-saas

# 4) Patch docker-compose.yml — add the odoo_ent service if missing.
if grep -q "container_name: odoo_saas_ent" "$COMPOSE"; then
    echo "[install] odoo_ent service already in compose, skipping"
else
    cp "$COMPOSE" "$COMPOSE.bak.enterprise.$(date +%s)"
    python3 - "$COMPOSE" << 'PY'
import sys, re
path = sys.argv[1]
with open(path) as f:
    content = f.read()

new_service = '''
  odoo_ent:
    image: clickbuild/odoo-enterprise:19
    container_name: odoo_saas_ent
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8169:8069"   # tenant HTTP (community uses 8069)
      - "127.0.0.1:8172:8072"   # longpolling (community uses 8072)
    volumes:
      - ./addons:/mnt/extra-addons
      - odoo_ent_data:/var/lib/odoo
      - ./cert-requests:/mnt/cert-requests
      - ./docker-enterprise/odoo-enterprise.conf:/etc/odoo/odoo.conf
    environment:
      - HOST=postgres
      - PORT=5432
      - USER=odoo
      - PASSWORD=${CLICKBUILD_ODOO_DB_PASSWORD:?CLICKBUILD_ODOO_DB_PASSWORD is required}
    networks:
      - odoo_net
'''

# Insert the new service just before the nginx service block (so dependencies
# are declared before the proxy).
m = re.search(r'^( {2}nginx:)', content, re.MULTILINE)
assert m, 'could not find nginx service header in docker-compose.yml'
content = content[:m.start()] + new_service + '\n' + content[m.start():]

# Also declare the volume in the bottom volumes: section.
if 'odoo_ent_data:' not in content:
    if re.search(r'^volumes:', content, re.MULTILINE):
        content = re.sub(r'(\nvolumes:[^\n]*\n(?:  [^\n]+\n)*)',
                         r'\1  odoo_ent_data:\n',
                         content, count=1)
    else:
        content = content.rstrip() + '\n\nvolumes:\n  odoo_ent_data:\n'

with open(path, 'w') as f:
    f.write(content)
print('[install] docker-compose.yml patched: +odoo_ent service +odoo_ent_data volume')
PY
fi

# 5) Bring the new container up.
echo "[install] starting odoo_ent ..."
docker compose up -d odoo_ent
sleep 5

# 6) Smoke check: did the container start?
if docker ps --format '{{.Names}} {{.Status}}' | grep -q '^odoo_saas_ent .*Up'; then
    echo "[install] ✓ odoo_saas_ent is up"
    docker exec odoo_saas_ent odoo --version 2>/dev/null | head -1
else
    echo "[install] ✗ odoo_saas_ent failed to start, last 30 log lines:"
    docker logs --tail 30 odoo_saas_ent 2>&1
    exit 1
fi
