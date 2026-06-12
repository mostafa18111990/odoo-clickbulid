#!/usr/bin/env python
"""
Setup Odoo Template DB - creates a pre-installed Odoo DB that new instances clone from.
This makes provisioning go from ~10 minutes to ~30 seconds.
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def run_print(cmd, label="", timeout=30):
    out, err = run(cmd, timeout)
    result = (out + err).strip()
    print(f"  [{label or cmd[:40]}] {result[:200]}")
    return out, err

TEMPLATE_DB   = "clickbuild_template"
TEMPLATE_PORT = 8099
PG_HOST       = "localhost"
PG_USER       = "clickbuild"
PG_PASS       = "CB_pg_S3cur3_2024!"
MASTER_PASS   = "m-uEzg510Fuqc9apChAXN1aGV4WDHgPk"

print("=" * 60)
print("Setting up Odoo Template DB")
print("=" * 60)

# Step 1: Check if template DB already exists
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
if out.strip() == "1":
    print(f"\n[INFO] Template DB '{TEMPLATE_DB}' already exists.")
    print("       To rebuild, drop it first: DROP DATABASE clickbuild_template;")
    client.close()
    sys.exit(0)

print(f"\n[1/4] Creating template database '{TEMPLATE_DB}'...")
run_print(
    f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -c "
    f"\"CREATE DATABASE {TEMPLATE_DB} OWNER {PG_USER}\"",
    "CREATE_DB", timeout=15
)

print(f"\n[2/4] Starting Odoo on port {TEMPLATE_PORT} to initialize template DB...")
print("      This will take 5-10 minutes. Please wait...")

# Start a temporary Odoo container for template initialization
template_cmd = (
    f"docker run -d --name odoo_template_setup "
    f"--network clickbuild-net "
    f"-p 127.0.0.1:{TEMPLATE_PORT}:8069 "
    f"-e DB_HOST={PG_HOST} "
    f"-e DB_PORT=5432 "
    f"-e DB_USER={PG_USER} "
    f"-e DB_PASSWORD={PG_PASS} "
    f"-e DB_NAME={TEMPLATE_DB} "
    f"-e MASTER_PASSWORD={MASTER_PASS} "
    f"-e ADMIN_EMAIL=admin@template.local "
    f"-e ADMIN_PASSWORD=admin123 "
    f"-e COMPANY_NAME='Template Company' "
    f"-e ODOO_MODULES=base,web "
    f"-e ODOO_LANG=ar_001,en_US "
    f"-e WITHOUT_DEMO=all "
    f"-e INIT_DB=true "
    f"-e ODOO_VERSION=19 "
    f"-m 1g "
    f"--cpus=1 "
    f"clickbuild/odoo:19"
)
run_print(template_cmd, "START_CONTAINER", timeout=30)

# Wait for Odoo to initialize (poll health endpoint)
print("\n[3/4] Waiting for Odoo to finish initializing DB...")
max_wait = 600  # 10 minutes
start    = time.time()
ready    = False

while time.time() - start < max_wait:
    elapsed = int(time.time() - start)
    out, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{TEMPLATE_PORT}/web/health", timeout=10)
    status = out.strip()
    print(f"  [{elapsed}s] HTTP {status}", flush=True)
    if status == "200":
        ready = True
        print(f"  Odoo ready after {elapsed} seconds!")
        break
    time.sleep(15)

if not ready:
    print("  [ERROR] Odoo did not initialize in time")
    run("docker stop odoo_template_setup && docker rm odoo_template_setup", timeout=30)
    client.close()
    sys.exit(1)

# Wait a bit more for full initialization
time.sleep(10)
print("  Waiting 10s for full initialization...")

print("\n[4/4] Stopping template container + marking DB as template...")
# Stop and remove the setup container
run_print("docker stop odoo_template_setup && docker rm odoo_template_setup", "STOP_CONTAINER", timeout=30)

# Mark the DB as a PostgreSQL template (allows fast cloning)
# Note: we can't use TEMPLATE mode directly because Odoo DBs have active connections
# Instead we keep it as a regular DB and use pg_dump/restore or createdb --template
print("  Template DB setup complete!")
print(f"  New instances will clone from '{TEMPLATE_DB}' instead of fresh init")
print(f"  Expected provisioning time: ~30 seconds vs ~10 minutes")

# Verify
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc \"SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
print(f"\n  Template DB: {out.strip()}")

sftp.close()
client.close()
print("\nTemplate setup complete!")
