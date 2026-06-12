#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix SSL for *.odoo.clickbulid.com
1. Remove includeSubDomains from HSTS (immediate fix)
2. Get wildcard cert via certbot DNS challenge
3. Add HTTPS server block for all subdomains
"""
import paramiko, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c

def run(c, cmd, timeout=120):
    print(f"\n$ {cmd[:120]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:2000])
    if err and not out: print(f"[err] {err[:400]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def main():
    c = connect()
    print("Connected")

    # ── Step 1: Read current config ─────────────────────────────────────────
    print("\n[1] Reading current Nginx config...")
    out, _ = run(c, "cat /etc/nginx/sites-available/clickbuild-platform-ssl")

    # ── Step 2: Fix HSTS — remove includeSubDomains + set max-age=0 to clear ─
    print("\n[2] Fixing HSTS header...")
    fix_hsts = r"""python3 << 'PYEOF'
path = '/etc/nginx/sites-available/clickbuild-platform-ssl'
with open(path) as f:
    content = f.read()

# First: set max-age=0 + includeSubDomains so browsers FORGET the HSTS policy
# This clears the subdomain enforcement from browser cache
OLD_HSTS = 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
NEW_HSTS  = 'add_header Strict-Transport-Security "max-age=0" always;  # Cleared includeSubDomains — wildcard cert pending'

if OLD_HSTS in content:
    content = content.replace(OLD_HSTS, NEW_HSTS)
    print("HSTS: cleared includeSubDomains")
elif 'includeSubDomains' in content:
    import re
    content = re.sub(
        r'add_header Strict-Transport-Security "[^"]*includeSubDomains[^"]*" always;',
        'add_header Strict-Transport-Security "max-age=0" always;  # Cleared',
        content
    )
    print("HSTS: cleared via regex")
else:
    print("HSTS header not found — checking content")
    for line in content.split('\n'):
        if 'Security' in line or 'HSTS' in line:
            print(f"  Found: {line.strip()}")

with open(path, 'w') as f:
    f.write(content)
print("Done")
PYEOF"""
    run(c, fix_hsts, timeout=30)

    # ── Step 3: Check if certbot-dns-cloudflare is available ─────────────────
    print("\n[3] Checking certbot plugins...")
    run(c, "certbot plugins 2>&1 | grep -i 'cloudflare\\|dns' || echo 'no dns plugins'")
    run(c, "pip3 show certbot-dns-cloudflare 2>/dev/null | head -3 || echo 'not installed'")

    # Install certbot-dns-cloudflare
    print("\n  Installing certbot-dns-cloudflare...")
    run(c, "pip3 install certbot-dns-cloudflare 2>&1 | tail -3 || apt-get install -y python3-certbot-dns-cloudflare 2>&1 | tail -5", timeout=60)

    # ── Step 4: Test nginx config and reload ─────────────────────────────────
    print("\n[4] Testing and reloading Nginx...")
    out, _ = run(c, "nginx -t 2>&1")
    if 'successful' in out or 'successful' in (run(c, "nginx -t 2>&1")[0]):
        run(c, "systemctl reload nginx")
        print("  Nginx reloaded!")

    # ── Step 5: Check if we have CF credentials already ──────────────────────
    print("\n[5] Checking for Cloudflare credentials...")
    run(c, "ls /root/.secrets/ 2>/dev/null || echo 'no secrets dir'")
    run(c, "cat /root/.secrets/cloudflare.ini 2>/dev/null | head -3 || echo 'no cloudflare.ini'")

    # ── Step 6: Try manual DNS challenge approach ─────────────────────────────
    print("\n[6] Current cert coverage:")
    run(c, "certbot certificates 2>&1 | head -30")

    # ── Step 7: Immediate HTTPS workaround with self-signed cert ─────────────
    # This lets Odoo subdomains load via HTTPS with a cert warning instead of hard block
    print("\n[7] Creating self-signed wildcard cert as immediate workaround...")
    run(c, """
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/self-signed-wildcard.key \
  -out /etc/ssl/self-signed-wildcard.crt \
  -subj "/C=SA/ST=Riyadh/L=Riyadh/O=ClickBuild/CN=*.odoo.clickbulid.com" \
  -addext "subjectAltName=DNS:*.odoo.clickbulid.com,DNS:odoo.clickbulid.com" 2>&1 | tail -3
""", timeout=30)

    run(c, "ls -la /etc/ssl/self-signed-wildcard.* 2>/dev/null")

    # ── Step 8: Add HTTPS server block for subdomains ─────────────────────────
    print("\n[8] Adding HTTPS subdomain server block...")

    # HTTPS_SUBDOMAIN_BLOCK is embedded in the heredoc below

    add_block = r"""python3 << 'PYEOF'
path = '/etc/nginx/sites-available/clickbuild-platform-ssl'
with open(path) as f:
    content = f.read()

MARKER = '# __ HTTPS for *.odoo.clickbulid.com'
if MARKER not in content and 'self-signed-wildcard' not in content:
    content += """
# __ HTTPS for *.odoo.clickbulid.com ___________________________________________
server {
    listen 443 ssl http2;
    server_name ~^(?<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;

    ssl_certificate     /etc/ssl/self-signed-wildcard.crt;
    ssl_certificate_key /etc/ssl/self-signed-wildcard.key;

    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 100M;
    proxy_read_timeout 300s;

    location / {
        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   X-Odoo-Subdomain  $sub;
        proxy_buffering    off;
    }
}
"""
    with open(path, 'w') as f:
        f.write(content)
    print("Added HTTPS subdomain block")
else:
    print("HTTPS block already present")
PYEOF"""
    run(c, add_block, timeout=30)

    # Test and reload
    out, err = run(c, "nginx -t 2>&1")
    if 'successful' in out or 'successful' in err:
        run(c, "systemctl reload nginx")
        print("  Nginx reloaded with HTTPS subdomain block!")
    else:
        print(f"  Nginx test issue: {out} {err}")

    # ── Step 9: Test HTTPS access ─────────────────────────────────────────────
    print("\n[9] Testing HTTPS subdomain access (with self-signed cert)...")
    time.sleep(2)
    # -k = allow self-signed
    out, _ = run(c, "curl -k -s -o /dev/null -w '%{http_code}' https://roaaa.odoo.clickbulid.com/web/login 2>/dev/null")
    print(f"  HTTPS roaaa (self-signed, -k): {out}")

    out, _ = run(c, "curl -s -o /dev/null -w '%{http_code}' http://roaaa.odoo.clickbulid.com/web/login 2>/dev/null")
    print(f"  HTTP roaaa: {out}")

    # ── Step 10: Summary ──────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("IMMEDIATE FIX APPLIED:")
    print("  1. HSTS max-age set to 0 (browsers will clear the policy)")
    print("  2. Self-signed wildcard cert created for *.odoo.clickbulid.com")
    print("  3. HTTPS server block added for subdomains")
    print()
    print("BROWSER STEPS (Firefox):")
    print("  Firefox -> Settings -> Privacy -> View Certificates -> Servers")
    print("  OR: about:config -> network.stricttransportsecurity.preloadlist = false")
    print("  OR simply: close Firefox completely, reopen")
    print()
    print("FOR PROPER WILDCARD CERT (once you have Cloudflare API token):")
    print("  1. Get token from: dash.cloudflare.com -> API Tokens -> Create Token")
    print("     Permission: Zone.DNS (Edit) for clickbulid.com")
    print("  2. Run: echo 'dns_cloudflare_api_token = YOUR_TOKEN' > /root/.secrets/cloudflare.ini")
    print("  3. chmod 600 /root/.secrets/cloudflare.ini")
    print("  4. certbot certonly --dns-cloudflare \\")
    print("       --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \\")
    print("       -d '*.odoo.clickbulid.com' -d 'odoo.clickbulid.com'")
    print("  5. Update nginx to use the new cert")
    print("="*60)

    c.close()

if __name__ == "__main__":
    main()
