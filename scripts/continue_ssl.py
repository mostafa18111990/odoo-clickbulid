#!/usr/bin/env python
"""Continue: check backend, get SSL, switch to HTTPS"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"
EMAIL  = "mostafahelmy1995@gmail.com"

# ─── 1. Fix backend (502 issue) ───────────────────────────────────────────────
print("Checking backend status...")
stdin, stdout, stderr = client.exec_command(
    "systemctl is-active clickbuild-api && "
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health"
)
status = stdout.read().decode().strip()
print(f"  Backend: {status}")

if '200' not in status:
    print("  Restarting backend...")
    stdin, stdout, stderr = client.exec_command(
        "systemctl restart clickbuild-api && sleep 3 && "
        "curl -s http://127.0.0.1:8000/api/health"
    )
    print(f"  -> {stdout.read().decode().strip()}")

# ─── 2. Get SSL cert via HTTP challenge (domain resolves = challenge will work)
print(f"\nGetting SSL for {DOMAIN}...")
certbot_cmd = (
    f"certbot certonly --nginx "
    f"-d {DOMAIN} "
    f"--non-interactive --agree-tos --email {EMAIL} 2>&1"
)
chan = client.get_transport().open_session()
chan.get_pty()
chan.exec_command(certbot_cmd)
start = time.time()
while not chan.exit_status_ready():
    if chan.recv_ready():
        data = chan.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    if time.time() - start > 120:
        print("\n[TIMEOUT]")
        break
    time.sleep(0.2)
remaining = chan.recv(65535).decode('utf-8', errors='replace')
if remaining: print(remaining)
cert_code = chan.recv_exit_status()
print(f"\nCertbot exit code: {cert_code}")

if cert_code != 0:
    print("Certbot failed. Trying webroot method...")
    certbot_cmd2 = (
        f"certbot certonly --webroot -w /var/www/html "
        f"-d {DOMAIN} "
        f"--non-interactive --agree-tos --email {EMAIL} 2>&1"
    )
    stdin, stdout, stderr = client.exec_command(certbot_cmd2, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace')
    print(out)
    # Check if cert exists anyway
    stdin, stdout, stderr = client.exec_command(f"ls /etc/letsencrypt/live/{DOMAIN}/ 2>&1")
    print("Cert files:", stdout.read().decode().strip())

# ─── 3. Verify cert exists ────────────────────────────────────────────────────
stdin, stdout, stderr = client.exec_command(f"ls /etc/letsencrypt/live/{DOMAIN}/ 2>&1")
cert_files = stdout.read().decode().strip()
print(f"\nCert files: {cert_files}")

if 'fullchain.pem' not in cert_files:
    print("No cert found!")
    sftp.close(); client.close(); sys.exit(1)

print("Certificate obtained!")

# ─── 4. Switch Nginx to HTTPS ─────────────────────────────────────────────────
print("\nSwitching to HTTPS config...")
cmds = [
    "rm -f /etc/nginx/sites-enabled/clickbuild-platform",
    "ln -sf /etc/nginx/sites-available/clickbuild-platform-ssl /etc/nginx/sites-enabled/clickbuild-platform",
    "nginx -t",
    "nginx -s reload",
    "echo HTTPS_OK",
]
stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.strip())
if err.strip(): print("STDERR:", err[:300])

# ─── 5. Update configs with HTTPS ─────────────────────────────────────────────
# Backend .env
stdin, stdout, stderr = client.exec_command("cat /opt/clickbuild/backend/.env")
env = stdout.read().decode('utf-8', errors='replace')
env_new = "\n".join(
    f"DOMAIN={DOMAIN}" if l.startswith("DOMAIN=") else
    f"ALLOWED_ORIGINS=https://{DOMAIN}" if l.startswith("ALLOWED_ORIGINS=") else
    f"FRONTEND_URL=https://{DOMAIN}" if l.startswith("FRONTEND_URL=") else l
    for l in env.splitlines()
) + "\n"
sftp.putfo(io.BytesIO(env_new.encode()), '/opt/clickbuild/backend/.env')
print("[OK] backend .env -> HTTPS")

# Frontend .env.local
new_env = f"NEXT_PUBLIC_API_URL=https://{DOMAIN}/api/v1\nNEXT_PUBLIC_DOMAIN={DOMAIN}\n"
sftp.putfo(io.BytesIO(new_env.encode()), '/opt/clickbuild/frontend/.env.local')
print("[OK] frontend .env.local -> HTTPS")

sftp.close()

# Restart backend
stdin, stdout, stderr = client.exec_command("systemctl restart clickbuild-api && sleep 2 && systemctl is-active clickbuild-api")
print(f"[OK] Backend: {stdout.read().decode().strip()}")

# ─── 6. Rebuild frontend ──────────────────────────────────────────────────────
print("\nRebuilding frontend with HTTPS URLs...")
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -12"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
b_code = stdout.channel.recv_exit_status()

if b_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | grep -E 'online|error'")
    print(stdout.read().decode().strip())

# ─── 7. Final test ────────────────────────────────────────────────────────────
time.sleep(3)
for url in [f"https://{DOMAIN}/api/health", f"https://{DOMAIN}/ar"]:
    stdin, stdout, stderr = client.exec_command(f"curl -sk -o /dev/null -w '%{{http_code}}' {url}")
    code = stdout.read().decode().strip()
    icon = "OK" if code in ['200','307','308'] else "FAIL"
    print(f"  [{icon}] {url} -> HTTP {code}")

# Auto-renewal cron
stdin, stdout, stderr = client.exec_command(
    "(crontab -l 2>/dev/null | grep -v certbot; "
    "echo '0 3 * * * certbot renew --quiet --nginx') | crontab - && echo CRON_OK"
)
print(stdout.read().decode().strip())

client.close()
print(f"\nDone! Site: https://{DOMAIN}")
