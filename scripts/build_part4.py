#!/usr/bin/env python3
"""Part 4 - Shell scripts + static icon + start Docker"""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

def upload(path, content):
    sftp = ssh.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

def run(cmd, timeout=60):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8','replace').strip()
    err = e.read().decode('utf-8','replace').strip()
    if out: print(out[:400])
    if err: print('ERR:', err[:300])
    return out

# ─────────────────────────────────────────────────────
# scripts/create_tenant.sh
# ─────────────────────────────────────────────────────
CREATE_TENANT_SH = """#!/bin/bash
# Usage: ./create_tenant.sh <subdomain> <company_name> [template_db]
set -euo pipefail

SUBDOMAIN="${1:?Subdomain required}"
COMPANY="${2:?Company name required}"
TEMPLATE="${3:-}"

DB_NAME="tenant_${SUBDOMAIN}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
PGPASSWORD="${DB_PASS:-odoo_pg_pass_2024}"
export PGPASSWORD

echo "Creating tenant: $SUBDOMAIN -> $DB_NAME"

# Validate subdomain
if ! echo "$SUBDOMAIN" | grep -qE '^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$'; then
    echo "ERROR: Invalid subdomain format"
    exit 1
fi

# Check if DB exists
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \\| -f 1 | grep -qw "$DB_NAME"; then
    echo "ERROR: Database $DB_NAME already exists"
    exit 1
fi

# Create DB
if [ -n "$TEMPLATE" ]; then
    echo "Creating from template: $TEMPLATE"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TEMPLATE' AND pid <> pg_backend_pid();"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
        -c "CREATE DATABASE \\"$DB_NAME\\" TEMPLATE \\"$TEMPLATE\\" OWNER \\"$DB_USER\\";"
else
    echo "Creating fresh database"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
        -c "CREATE DATABASE \\"$DB_NAME\\" OWNER \\"$DB_USER\\" ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;"
fi

# Create filestore
mkdir -p "/var/lib/odoo/filestore/$DB_NAME"

echo "✅ Tenant $SUBDOMAIN created. Database: $DB_NAME"
echo "   URL: https://$SUBDOMAIN.myerp.com"
"""

# ─────────────────────────────────────────────────────
# scripts/backup_tenant.sh
# ─────────────────────────────────────────────────────
BACKUP_SH = """#!/bin/bash
# Usage: ./backup_tenant.sh <db_name>
set -euo pipefail

DB_NAME="${1:?Database name required}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
PGPASSWORD="${DB_PASS:-odoo_pg_pass_2024}"
export PGPASSWORD

BACKUP_DIR="/opt/odoo-saas/backups/$DB_NAME"
TS=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "Backing up database: $DB_NAME"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"
echo "  DB dump: $BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"

# Backup filestore
FS_PATH="/var/lib/odoo/filestore/$DB_NAME"
if [ -d "$FS_PATH" ]; then
    tar -czf "$BACKUP_DIR/${DB_NAME}_filestore_${TS}.tar.gz" -C "/var/lib/odoo/filestore" "$DB_NAME"
    echo "  Filestore: $BACKUP_DIR/${DB_NAME}_filestore_${TS}.tar.gz"
fi

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm --
echo "✅ Backup complete for $DB_NAME"
"""

# ─────────────────────────────────────────────────────
# scripts/restore_tenant.sh
# ─────────────────────────────────────────────────────
RESTORE_SH = """#!/bin/bash
# Usage: ./restore_tenant.sh <db_name> <backup_file.sql.gz>
set -euo pipefail

DB_NAME="${1:?Database name required}"
BACKUP_FILE="${2:?Backup file required}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
PGPASSWORD="${DB_PASS:-odoo_pg_pass_2024}"
export PGPASSWORD

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring $DB_NAME from $BACKUP_FILE"

# Terminate existing connections
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();"

# Drop and recreate
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres -c "DROP DATABASE IF EXISTS \\"$DB_NAME\\";"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
    -c "CREATE DATABASE \\"$DB_NAME\\" OWNER \\"$DB_USER\\" ENCODING 'UTF8';"

# Restore
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

echo "✅ Restore complete for $DB_NAME"
"""

# ─────────────────────────────────────────────────────
# scripts/drop_tenant.sh
# ─────────────────────────────────────────────────────
DROP_SH = """#!/bin/bash
# Usage: ./drop_tenant.sh <db_name>
set -euo pipefail

DB_NAME="${1:?Database name required}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
PGPASSWORD="${DB_PASS:-odoo_pg_pass_2024}"
export PGPASSWORD

echo "⚠️  WARNING: This will permanently delete database: $DB_NAME"
read -p "Type the database name to confirm: " CONFIRM

if [ "$CONFIRM" != "$DB_NAME" ]; then
    echo "Cancelled."
    exit 1
fi

# Backup first
echo "Creating safety backup..."
BACKUP_DIR="/opt/odoo-saas/backups/$DB_NAME"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_FINAL_${TS}.sql.gz"
echo "  Safety backup saved."

# Terminate connections
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();"

# Drop DB
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" postgres -c "DROP DATABASE IF EXISTS \\"$DB_NAME\\";"

# Remove filestore
FS_PATH="/var/lib/odoo/filestore/$DB_NAME"
if [ -d "$FS_PATH" ]; then
    rm -rf "$FS_PATH"
    echo "  Filestore removed."
fi

echo "✅ Tenant $DB_NAME deleted."
"""

# ─────────────────────────────────────────────────────
# scripts/init_ssl.sh — get wildcard cert
# ─────────────────────────────────────────────────────
SSL_SH = """#!/bin/bash
# Get SSL certificate for myerp.com + *.myerp.com
# Run this ONCE before starting containers
# Requires certbot installed on host

DOMAIN="myerp.com"
EMAIL="admin@myerp.com"

certbot certonly \\
    --standalone \\
    --preferred-challenges http \\
    -d "$DOMAIN" \\
    -d "*.$DOMAIN" \\
    --agree-tos \\
    --email "$EMAIL" \\
    --non-interactive \\
    --expand

echo "✅ SSL certificate obtained for $DOMAIN"
echo "   Cert path: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
"""

# ─────────────────────────────────────────────────────
# scripts/start.sh — start everything
# ─────────────────────────────────────────────────────
START_SH = """#!/bin/bash
cd /opt/odoo-saas

echo "Starting SaaS platform..."
docker compose pull
docker compose up -d

echo ""
echo "Waiting for services..."
sleep 15

echo "Status:"
docker compose ps

echo ""
echo "✅ Platform started!"
echo "   Admin panel: https://admin.myerp.com"
echo "   Odoo logs:   docker compose logs -f odoo"
"""

# ─────────────────────────────────────────────────────
# Static description icon (minimal 1x1 PNG placeholder)
# ─────────────────────────────────────────────────────
# A minimal valid PNG (1x1 green pixel)
ICON_B64 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)

print('── Uploading scripts ──')
upload('/opt/odoo-saas/scripts/create_tenant.sh', CREATE_TENANT_SH)
upload('/opt/odoo-saas/scripts/backup_tenant.sh', BACKUP_SH)
upload('/opt/odoo-saas/scripts/restore_tenant.sh', RESTORE_SH)
upload('/opt/odoo-saas/scripts/drop_tenant.sh', DROP_SH)
upload('/opt/odoo-saas/scripts/init_ssl.sh', SSL_SH)
upload('/opt/odoo-saas/scripts/start.sh', START_SH)

# Make scripts executable
run('chmod +x /opt/odoo-saas/scripts/*.sh')

# Upload icon
sftp = ssh.open_sftp()
with sftp.open('/opt/odoo-saas/addons/saas_tenant_manager/static/description/icon.png', 'wb') as f:
    f.write(ICON_B64)
sftp.close()
print('  ✅ static/description/icon.png')

# ─────────────────────────────────────────────────────
# Verify full structure
# ─────────────────────────────────────────────────────
print('\n── Verifying structure ──')
run('find /opt/odoo-saas -type f | sort')

# Install Docker if not present
print('\n── Checking Docker ──')
result = run('docker --version 2>/dev/null || echo MISSING')
if 'MISSING' in result:
    print('Installing Docker...')
    run('curl -fsSL https://get.docker.com | sh', timeout=120)
    run('systemctl enable docker && systemctl start docker')
else:
    print('Docker OK:', result)

# Install Docker Compose plugin if needed
result = run('docker compose version 2>/dev/null || echo MISSING')
if 'MISSING' in result:
    run('apt-get install -y docker-compose-plugin 2>/dev/null || pip3 install docker-compose')

print('\n✅ Part 4 done!')
print('\n── Project ready at /opt/odoo-saas ──')
print('To start: cd /opt/odoo-saas && docker compose up -d')
ssh.close()
