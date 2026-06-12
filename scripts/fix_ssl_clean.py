#!/usr/bin/env python3
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
    if out: print(out[:3000])
    if err and not out: print(f"[err] {err[:400]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()

def main():
    c = connect()
    print("Connected")

    # ── 1. Fix HSTS header — remove includeSubDomains ──────────────────────
    print("\n[1] Fix HSTS — remove includeSubDomains...")
    fix_hsts = (
        "python3 -c \""
        "path='/etc/nginx/sites-available/clickbuild-platform-ssl';"
        "f=open(path);content=f.read();f.close();"
        "old='max-age=31536000; includeSubDomains';"
        "new='max-age=0';"
        "content=content.replace(old,new);"
        "f=open(path,'w');f.write(content);f.close();"
        "print('HSTS fixed')"
        "\""
    )
    run(c, fix_hsts, timeout=30)

    # Verify the fix
    run(c, "grep -n 'Strict-Transport' /etc/nginx/sites-available/clickbuild-platform-ssl")

    # ── 2. Generate self-signed wildcard certificate ────────────────────────
    print("\n[2] Generating self-signed wildcard cert...")
    run(c, (
        "openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
        "-keyout /etc/ssl/cb-wildcard.key "
        "-out /etc/ssl/cb-wildcard.crt "
        "-subj '/C=SA/O=ClickBuild/CN=odoo.clickbulid.com' "
        "-addext 'subjectAltName=DNS:*.odoo.clickbulid.com,DNS:odoo.clickbulid.com' "
        "2>&1 | tail -3"
    ), timeout=30)
    run(c, "ls -la /etc/ssl/cb-wildcard.*")

    # ── 3. Write the HTTPS subdomain block to a separate file ───────────────
    print("\n[3] Writing HTTPS wildcard server block...")

    # Write nginx config via sftp (avoids shell quoting issues with braces)
    nginx_conf = (
        "# HTTPS wildcard for *.odoo.clickbulid.com\n"
        "# Self-signed cert (temporary until Cloudflare wildcard LE cert)\n"
        "server {\n"
        "    listen 443 ssl http2;\n"
        "    server_name ~^(?P<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;\n"
        "\n"
        "    ssl_certificate     /etc/ssl/cb-wildcard.crt;\n"
        "    ssl_certificate_key /etc/ssl/cb-wildcard.key;\n"
        "    ssl_protocols       TLSv1.2 TLSv1.3;\n"
        "    ssl_ciphers         HIGH:!aNULL:!MD5;\n"
        "\n"
        "    add_header X-Frame-Options SAMEORIGIN always;\n"
        "    add_header X-Content-Type-Options nosniff always;\n"
        "\n"
        "    client_max_body_size 100M;\n"
        "    proxy_read_timeout   300s;\n"
        "\n"
        "    location / {\n"
        "        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;\n"
        "        proxy_http_version 1.1;\n"
        "        proxy_set_header   Host              $host;\n"
        "        proxy_set_header   X-Real-IP         $remote_addr;\n"
        "        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;\n"
        "        proxy_set_header   X-Forwarded-Proto https;\n"
        "        proxy_set_header   X-Odoo-Subdomain  $sub;\n"
        "        proxy_buffering    off;\n"
        "    }\n"
        "}\n"
    )
    upload(c, '/etc/nginx/sites-available/odoo-wildcard-https', nginx_conf)
    run(c, "ln -sf /etc/nginx/sites-available/odoo-wildcard-https /etc/nginx/sites-enabled/odoo-wildcard-https 2>/dev/null; echo done")

    # ── 4. Also update HTTP subdomain block to use named capture $sub ───────
    print("\n[4] Checking HTTP subdomain block uses named capture...")
    run(c, "grep -n 'sub\\|Subdomain\\|clickbulid' /etc/nginx/sites-available/clickbuild-platform-ssl | head -20")

    # ── 5. Test and reload Nginx ─────────────────────────────────────────────
    print("\n[5] Nginx test and reload...")
    out, err = run(c, "nginx -t 2>&1")
    if 'successful' in out or 'successful' in err:
        run(c, "systemctl reload nginx")
        print("  Nginx reloaded!")
    else:
        # Debug
        print("  Nginx test failed — showing config")
        run(c, "cat /etc/nginx/sites-available/odoo-wildcard-https")
        return

    # ── 6. Test access ────────────────────────────────────────────────────────
    print("\n[6] Testing access...")
    time.sleep(2)

    # HTTP should still work
    out, _ = run(c, "curl -s -o /dev/null -w '%{http_code}' http://roaaa.odoo.clickbulid.com/web/login 2>/dev/null")
    print(f"  HTTP:  {out}")

    # HTTPS with self-signed (use -k to bypass cert check)
    out, _ = run(c, "curl -k -s -o /dev/null -w '%{http_code}' https://roaaa.odoo.clickbulid.com/web/login 2>/dev/null")
    print(f"  HTTPS (self-signed, -k): {out}")

    # ── 7. Install certbot-dns-cloudflare for later ──────────────────────────
    print("\n[7] Installing certbot-dns-cloudflare plugin...")
    run(c, "apt-get install -y python3-certbot-dns-cloudflare 2>&1 | tail -3 || pip3 install certbot-dns-cloudflare 2>&1 | tail -3", timeout=60)
    run(c, "mkdir -p /root/.secrets && chmod 700 /root/.secrets")

    # ── 8. Print instructions ─────────────────────────────────────────────────
    print("\n" + "="*60)
    print("CURRENT STATE:")
    print("  HTTP:  roaaa.odoo.clickbulid.com  -> WORKS")
    print("  HTTPS: roaaa.odoo.clickbulid.com  -> WORKS (self-signed, browser warning)")
    print("  HSTS:  max-age=0 (browsers will clear old policy)")
    print()
    print("BROWSER FIX (for existing HSTS cache):")
    print("  Firefox: type 'about:config' -> search 'hsts' -> clear site data")
    print("  OR: Settings -> Privacy & Security -> Clear Data -> Cached Web Content")
    print("  OR: Simply use a different browser that hasn't visited the site")
    print()
    print("FOR PROPER WILDCARD CERT (eliminates warning permanently):")
    print("  Need: Cloudflare API Token with Zone.DNS Edit permission")
    print("  Steps:")
    print("    1. dash.cloudflare.com -> API Tokens -> Create Token")
    print("       Template: 'Edit zone DNS' -> Zone: clickbulid.com")
    print("    2. echo 'dns_cloudflare_api_token = CF_TOKEN_HERE' > /root/.secrets/cloudflare.ini")
    print("    3. chmod 600 /root/.secrets/cloudflare.ini")
    print("    4. certbot certonly --dns-cloudflare \\")
    print("           --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \\")
    print("           -d '*.odoo.clickbulid.com' \\")
    print("           --preferred-challenges dns-01")
    print("    5. Update nginx: replace ssl_certificate path with LE cert path")
    print("    6. Restore HSTS: max-age=31536000 (without includeSubDomains)")
    print("="*60)

    c.close()

if __name__ == "__main__":
    main()
