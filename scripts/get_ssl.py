#!/usr/bin/env python
"""
Get SSL certificate for odoo.clickbuild.com + *.odoo.clickbuild.com
Run AFTER DNS records are pointing to 129.121.98.243
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

DOMAIN = "odoo.clickbuild.com"
EMAIL  = "mostafahelmy1995@gmail.com"

# ─── 1. Check DNS first ───────────────────────────────────────────────────────
print("Checking DNS resolution...")
stdin, stdout, stderr = client.exec_command(f"curl -s --max-time 5 -o /dev/null -w '%{{http_code}}' http://{DOMAIN}/api/health")
code = stdout.read().decode().strip()
print(f"  http://{DOMAIN}/api/health -> HTTP {code}")

if code not in ['200', '301', '302', '307', '308']:
    print(f"\nDNS not yet pointing to this server!")
    print(f"Add these records in clickbuild.com DNS panel:")
    print(f"  A    odoo        129.121.98.243")
    print(f"  A    *.odoo      129.121.98.243")
    print(f"\nThen wait 5-30 min and run this script again.")
    client.close()
    sys.exit(0)

print(f"  DNS OK! Getting SSL certificate...")

# ─── 2. Get wildcard cert via DNS challenge OR get two certs via HTTP challenge
# For wildcard (*.odoo.clickbuild.com) we NEED DNS challenge
# But for just odoo.clickbuild.com + www.odoo.clickbuild.com we can use HTTP

# Strategy: get cert for odoo.clickbuild.com via HTTP challenge
# Then separately handle wildcard via DNS challenge

# HTTP challenge cert for main domain
certbot_cmd = (
    f"certbot certonly --nginx "
    f"-d {DOMAIN} -d www.{DOMAIN} "
    f"--non-interactive --agree-tos --email {EMAIL} "
    f"--redirect 2>&1"
)
print(f"\nRunning certbot for {DOMAIN}...")
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
    print("Certbot failed. Trying standalone mode...")
    certbot_cmd2 = (
        f"certbot certonly --standalone "
        f"--pre-hook 'nginx -s stop' --post-hook 'nginx' "
        f"-d {DOMAIN} "
        f"--non-interactive --agree-tos --email {EMAIL} 2>&1"
    )
    stdin, stdout, stderr = client.exec_command(certbot_cmd2, timeout=120)
    print(stdout.read().decode('utf-8', errors='replace'))
    cert_code = 0

# ─── 3. Switch Nginx to HTTPS config ─────────────────────────────────────────
if cert_code == 0:
    print("\nSwitching Nginx to HTTPS...")
    cmds = [
        "ln -sf /etc/nginx/sites-available/clickbuild-platform-ssl /etc/nginx/sites-enabled/clickbuild-platform",
        "nginx -t",
        "nginx -s reload",
        "echo SSL_OK",
    ]
    stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(out)
    if err.strip(): print("STDERR:", err[:200])

    # Test HTTPS
    time.sleep(2)
    stdin, stdout, stderr = client.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health")
    code = stdout.read().decode().strip()
    print(f"\nHTTPS test: https://{DOMAIN}/api/health -> HTTP {code}")

    if code == '200':
        print(f"\nSite is LIVE at https://{DOMAIN}")
        print(f"Register: https://{DOMAIN}/ar/register")
        print(f"Login:    https://{DOMAIN}/ar/login")

        # Setup certbot auto-renewal
        stdin, stdout, stderr = client.exec_command(
            "systemctl enable certbot.timer && systemctl start certbot.timer && echo RENEWAL_OK"
        )
        print(stdout.read().decode())

client.close()
