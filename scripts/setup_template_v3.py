#!/usr/bin/env python
"""
Setup Odoo Template DB v3 - uses correct entrypoint + gateway IP
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
    print(f"  [{label}] {r[:300]}")
    return out, err

TEMPLATE_DB   = "clickbuild_template"
TEMPLATE_PORT = 8099
DOCKER_GW     = "172.18.0.1"
PG_HOST       = "localhost"
PG_USER       = "clickbuild"
PG_PASS       = "CB_pg_S3cur3_2024!"
MASTER_PASS   = "m-uEzg510Fuqc9apChAXN1aGV4WDHgPk"

print("=" * 60)
print("Setting up Odoo Template DB v3")
print("=" * 60)

# Cleanup
rp("docker stop odoo_template_setup 2>/dev/null; docker rm odoo_template_setup 2>/dev/null; echo CLEAN", "CLEANUP")

# Drop empty template if exists
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
if out.strip() == "1":
    rp(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -c 'DROP DATABASE {TEMPLATE_DB}'", "DROP_OLD")

print(f"\n[1/4] Creating template database...")
rp(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -c \"CREATE DATABASE {TEMPLATE_DB} OWNER {PG_USER}\"", "CREATE_DB")

print(f"\n[2/4] Starting Odoo to initialize template DB (10-15 min)...")
start_cmd = (
    f"docker run -d --name odoo_template_setup "
    f"--entrypoint /entrypoint.sh "
    f"--network clickbuild-net "
    f"--add-host=dockerhost:{DOCKER_GW} "
    f"-p 127.0.0.1:{TEMPLATE_PORT}:8069 "
    f"-e DB_HOST={DOCKER_GW} "
    f"-e DB_PORT=5432 "
    f"-e DB_USER={PG_USER} "
    f"-e DB_PASSWORD={PG_PASS} "
    f"-e DB_NAME={TEMPLATE_DB} "
    f"-e MASTER_PASSWORD={MASTER_PASS} "
    f"-e ADMIN_EMAIL=admin@template.local "
    f"-e ADMIN_PASSWORD=Admin123! "
    f"-e COMPANY_NAME=Template "
    f"-e ODOO_MODULES=base,web "
    f"-e ODOO_LANG=ar_001,en_US "
    f"-e WITHOUT_DEMO=all "
    f"-e INIT_DB=true "
    f"-e ODOO_VERSION=19 "
    f"-e SMTP_HOST=smtp.gmail.com "
    f"-e SMTP_PORT=587 "
    f"-e SMTP_SSL=true "
    f"-e SMTP_USER=noreply@clickbuild.com "
    f"-e SMTP_PASSWORD=dummy "
    f"-e EMAIL_FROM=noreply@clickbuild.com "
    f"-m 1g --cpus=1 "
    f"clickbuild/odoo:19"
)
rp(start_cmd, "START")

time.sleep(5)
out, _ = run("docker inspect odoo_template_setup --format '{{.State.Status}}' 2>/dev/null", timeout=5)
print(f"  Container status: {out.strip()}")
rp("docker logs odoo_template_setup 2>&1 | head -20", "EARLY_LOGS")

print(f"\n[3/4] Polling until Odoo is ready...")
max_wait = 900
start    = time.time()
ready    = False

while time.time() - start < max_wait:
    elapsed = int(time.time() - start)

    # Check container state
    out, _ = run("docker inspect odoo_template_setup --format '{{.State.Status}}' 2>/dev/null", timeout=5)
    status = out.strip()
    if status not in ("running", ""):
        print(f"  [{elapsed}s] Container state: {status} — checking logs...")
        out_logs, _ = run("docker logs odoo_template_setup 2>&1 | tail -20", timeout=10)
        print(out_logs)
        break

    out, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{TEMPLATE_PORT}/web/health", timeout=10)
    http   = out.strip()
    print(f"  [{elapsed}s] Status={status} HTTP={http}", flush=True)

    if http == "200":
        ready = True
        print(f"\n  ✓ Odoo ready in {elapsed}s!")
        break
    time.sleep(20)

if not ready:
    print("\n  [FAIL] Template setup failed. Container logs:")
    rp("docker logs odoo_template_setup 2>&1 | tail -50", "LOGS", timeout=15)
    rp("docker stop odoo_template_setup && docker rm odoo_template_setup", "CLEANUP", timeout=20)
    client.close()
    sys.exit(1)

time.sleep(5)
print("\n[4/4] Stopping template container (keeping DB)...")
rp("docker stop odoo_template_setup && docker rm odoo_template_setup", "STOP", timeout=30)

# Verify
out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d postgres -tAc "
             f"\"SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname='{TEMPLATE_DB}'\"")
print(f"\n  Template DB: {out.strip()}")

out, _ = run(f"PGPASSWORD='{PG_PASS}' psql -h {PG_HOST} -U {PG_USER} -d {TEMPLATE_DB} -tAc "
             "\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\"")
print(f"  Tables: {out.strip()}")

print(f"\n✅ Template DB ready!")
print(f"   New instances will clone '{TEMPLATE_DB}' (~30s) instead of fresh init (~10-15min)")
client.close()
