#!/usr/bin/env python
"""
Setup Odoo Template DB v2
Uses host-gateway so container can reach host PostgreSQL
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def rp(cmd, label="", timeout=30):
    out, err = run(cmd, timeout)
    r = (out + err).strip()
    print(f"  [{label or '?'}] {r[:300]}")
    return out, err

TEMPLATE_DB   = "clickbuild_template"
TEMPLATE_PORT = 8099
PG_HOST       = "localhost"
PG_USER       = "clickbuild"
PG_PASS       = "CB_pg_S3cur3_2024!"
MASTER_PASS   = "m-uEzg510Fuqc9apChAXN1aGV4WDHgPk"

print("=" * 60)
print("Setting up Odoo Template DB v2")
print("=" * 60)

# Cleanup stale container if exists
rp("docker stop odoo_template_setup 2>/dev/null; docker rm odoo_template_setup 2>/dev/null; echo CLEAN", "CLEANUP")

# Check if template DB already exists
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
if out.strip() == "1":
    print(f"\n[INFO] Template DB '{TEMPLATE_DB}' already exists. Skipping.")
    print("       Delete it first to rebuild: DROP DATABASE clickbuild_template;")
    client.close()
    sys.exit(0)

# Get Docker host gateway IP (so container can reach host Postgres)
out, _ = run("docker network inspect clickbuild-net --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}'")
docker_gw = out.strip()
if not docker_gw:
    # fallback: get host IP from default bridge
    out, _ = run("ip route show default | awk '/default/ {print $3}' | head -1")
    docker_gw = out.strip() or "172.17.0.1"
print(f"\n[INFO] Docker gateway: {docker_gw} (used for Postgres access from container)")

# Allow PostgreSQL to accept connections from Docker network
rp(f"grep -q 'host all all {docker_gw}/8' /etc/postgresql/*/pg_hba.conf 2>/dev/null || "
   f"(echo 'host all all {docker_gw}/8 md5' >> /etc/postgresql/16/main/pg_hba.conf && "
   f"systemctl reload postgresql && echo ADDED_HBA) || echo ALREADY_OK", "PG_HBA")

# Make PostgreSQL listen on docker gateway
rp("sed -i \"s/#listen_addresses = 'localhost'/listen_addresses = '*'/\" /etc/postgresql/16/main/postgresql.conf 2>/dev/null; "
   "grep listen_addresses /etc/postgresql/16/main/postgresql.conf | head -2", "PG_LISTEN")
rp("systemctl reload postgresql && echo PG_RELOADED", "PG_RELOAD")

print(f"\n[1/4] Creating template database '{TEMPLATE_DB}'...")
rp(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -c "
   f"\"CREATE DATABASE {TEMPLATE_DB} OWNER {PG_USER}\"", "CREATE_DB")

print(f"\n[2/4] Starting Odoo container (using docker host gateway {docker_gw} for DB)...")
rp(f"docker run -d --name odoo_template_setup "
   f"--network clickbuild-net "
   f"--add-host=dockerhost:{docker_gw} "
   f"-p 127.0.0.1:{TEMPLATE_PORT}:8069 "
   f"-e DB_HOST={docker_gw} "
   f"-e DB_PORT=5432 "
   f"-e DB_USER={PG_USER} "
   f"-e DB_PASSWORD={PG_PASS} "
   f"-e DB_NAME={TEMPLATE_DB} "
   f"-e MASTER_PASSWORD={MASTER_PASS} "
   f"-e ADMIN_EMAIL=admin@template.local "
   f"-e ADMIN_PASSWORD=Admin123! "
   f"-e COMPANY_NAME='Template' "
   f"-e ODOO_MODULES=base,web "
   f"-e ODOO_LANG=ar_001,en_US "
   f"-e WITHOUT_DEMO=all "
   f"-e INIT_DB=true "
   f"-e ODOO_VERSION=19 "
   f"-m 1g --cpus=1 "
   f"clickbuild/odoo:19", "START")

# Wait a moment then check container status
time.sleep(5)
rp("docker ps --filter name=odoo_template_setup --format 'Status: {{.Status}}'", "STATUS")
rp("docker logs odoo_template_setup 2>&1 | head -20", "LOGS")

print(f"\n[3/4] Waiting for Odoo initialization (up to 15 minutes)...")
max_wait = 900
start = time.time()
ready = False

while time.time() - start < max_wait:
    elapsed = int(time.time() - start)

    # Check if container is still running
    out, _ = run("docker inspect odoo_template_setup --format '{{.State.Status}}' 2>/dev/null", timeout=5)
    if out.strip() not in ("running", ""):
        print(f"  [{elapsed}s] Container stopped! Checking logs...")
        rp("docker logs odoo_template_setup 2>&1 | tail -30", "ERROR_LOGS")
        break

    out, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{TEMPLATE_PORT}/web/health", timeout=10)
    status = out.strip()
    print(f"  [{elapsed}s] HTTP {status}", flush=True)

    if status == "200":
        ready = True
        print(f"  ✓ Odoo ready after {elapsed} seconds!")
        break
    time.sleep(20)

if not ready:
    print("\n  [FAIL] Odoo did not initialize.")
    rp("docker logs odoo_template_setup 2>&1 | tail -40", "FINAL_LOGS")
    rp("docker stop odoo_template_setup && docker rm odoo_template_setup", "CLEANUP")
    client.close()
    sys.exit(1)

time.sleep(10)

print("\n[4/4] Stopping template container...")
rp("docker stop odoo_template_setup && docker rm odoo_template_setup", "STOP")

# Verify
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc "
             f"\"SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
print(f"\n  Template DB: {out.strip()}")
print(f"\n✅ Template setup complete!")
print(f"   New instances will clone '{TEMPLATE_DB}' (~30s) instead of fresh init (~10min)")

client.close()
