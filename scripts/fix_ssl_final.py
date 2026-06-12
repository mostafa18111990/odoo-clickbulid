#!/usr/bin/env python3
import paramiko, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"
EMAIL = "mostafahelmy1995@gmail.com"

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
    if err and not out: print(f"[err] {err[:500]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def nginx_https_conf(sub):
    domain = sub + ".odoo.clickbulid.com"
    lines = [
        "server {",
        "    listen 443 ssl http2;",
        "    server_name " + domain + ";",
        "",
        "    ssl_certificate     /etc/letsencrypt/live/" + domain + "/fullchain.pem;",
        "    ssl_certificate_key /etc/letsencrypt/live/" + domain + "/privkey.pem;",
        "    include             /etc/letsencrypt/options-ssl-nginx.conf;",
        "    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;",
        "",
        "    add_header X-Frame-Options SAMEORIGIN always;",
        "    add_header X-Content-Type-Options nosniff always;",
        "    client_max_body_size 100M;",
        "    proxy_read_timeout   300s;",
        "",
        "    location /.well-known/acme-challenge/ { root /var/www/html; }",
        "",
        "    location / {",
        "        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;",
        "        proxy_http_version 1.1;",
        "        proxy_set_header   Host              $host;",
        "        proxy_set_header   X-Real-IP         $remote_addr;",
        "        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;",
        "        proxy_set_header   X-Forwarded-Proto https;",
        "        proxy_set_header   X-Odoo-Subdomain  " + sub + ";",
        "        proxy_buffering    off;",
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"

def provisioning_helper():
    """Returns the SSL helper code to inject into provisioning.py"""
    lines = [
        "",
        "import subprocess as _ssl_sp",
        "import os as _ssl_os",
        "",
        "def _issue_ssl_cert(subdomain):",
        "    import logging",
        "    logger = logging.getLogger(__name__)",
        "    domain = subdomain + '.odoo.clickbulid.com'",
        "    cert_path = '/etc/letsencrypt/live/' + domain + '/fullchain.pem'",
        "    if _ssl_os.path.exists(cert_path):",
        "        _write_instance_nginx(subdomain)",
        "        return True",
        "    try:",
        "        r = _ssl_sp.run([",
        "            'certbot', 'certonly', '--webroot',",
        "            '-w', '/var/www/html', '-d', domain,",
        "            '--non-interactive', '--agree-tos',",
        "            '-m', 'mostafahelmy1995@gmail.com', '--quiet',",
        "        ], capture_output=True, text=True, timeout=120)",
        "        if r.returncode == 0:",
        "            logger.info('SSL cert issued for ' + domain)",
        "            _write_instance_nginx(subdomain)",
        "            return True",
        "        else:",
        "            logger.warning('certbot failed for ' + domain + ': ' + r.stderr[:200])",
        "            return False",
        "    except Exception as e:",
        "        logger.warning('SSL cert failed for ' + domain + ': ' + str(e))",
        "        return False",
        "",
        "def _write_instance_nginx(subdomain):",
        "    import subprocess",
        "    domain = subdomain + '.odoo.clickbulid.com'",
        "    conf_dir = '/etc/nginx/sites-available/instances'",
        "    _ssl_os.makedirs(conf_dir, exist_ok=True)",
        "    conf_path = conf_dir + '/' + subdomain + '.conf'",
        "    enabled  = '/etc/nginx/sites-enabled/' + subdomain + '.conf'",
        "    ledir = '/etc/letsencrypt/live/' + domain",
        "    cfg_lines = [",
        "        'server {',",
        "        '    listen 443 ssl http2;',",
        "        '    server_name ' + domain + ';',",
        "        '    ssl_certificate     ' + ledir + '/fullchain.pem;',",
        "        '    ssl_certificate_key ' + ledir + '/privkey.pem;',",
        "        '    include             /etc/letsencrypt/options-ssl-nginx.conf;',",
        "        '    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;',",
        "        '    add_header X-Frame-Options SAMEORIGIN always;',",
        "        '    client_max_body_size 100M;',",
        "        '    proxy_read_timeout 300s;',",
        "        '    location /.well-known/acme-challenge/ { root /var/www/html; }',",
        "        '    location / {',",
        "        '        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;',",
        "        '        proxy_http_version 1.1;',",
        "        '        proxy_set_header   Host              $host;',",
        "        '        proxy_set_header   X-Real-IP         $remote_addr;',",
        "        '        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;',",
        "        '        proxy_set_header   X-Forwarded-Proto https;',",
        "        '        proxy_set_header   X-Odoo-Subdomain  ' + subdomain + ';',",
        "        '        proxy_buffering    off;',",
        "        '    }',",
        "        '}',",
        "    ]",
        "    with open(conf_path, 'w') as f:",
        "        f.write('\\n'.join(cfg_lines) + '\\n')",
        "    if not _ssl_os.path.exists(enabled):",
        "        _ssl_os.symlink(conf_path, enabled)",
        "    subprocess.run(['nginx', '-t'], capture_output=True)",
        "    subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)",
        "",
    ]
    return "\n".join(lines)

def main():
    c = connect()
    print("Connected")

    # ── 1. Ensure ACME challenge path works ─────────────────────────────────
    print("\n[1] Testing ACME challenge path...")
    run(c, "mkdir -p /var/www/html/.well-known/acme-challenge")
    run(c, "echo ok > /var/www/html/.well-known/acme-challenge/ping")
    out, _ = run(c, "curl -s http://roaaa.odoo.clickbulid.com/.well-known/acme-challenge/ping 2>/dev/null")

    if "ok" not in out:
        print("  ACME path not working — fixing nginx subdomain block...")
        # Add acme location to http subdomain block if missing
        fix = (
            "python3 -c \""
            "p='/etc/nginx/sites-available/clickbuild-platform-ssl';"
            "f=open(p);s=f.read();f.close();"
            "acme='    location /.well-known/acme-challenge/ { root /var/www/html; }';"
            "loc='    location / {';"
            "s=s.replace(loc, acme+'\\n\\n'+loc, 1) if acme not in s else s;"
            "f=open(p,'w');f.write(s);f.close();print('done')"
            "\""
        )
        run(c, fix)
        run(c, "nginx -t 2>&1 && systemctl reload nginx")
        time.sleep(2)
        out, _ = run(c, "curl -s http://roaaa.odoo.clickbulid.com/.well-known/acme-challenge/ping 2>/dev/null")
        print(f"  After fix: '{out}'")
    else:
        print("  ACME challenge path: OK")

    run(c, "rm -f /var/www/html/.well-known/acme-challenge/ping")

    # ── 2. Get running instances ─────────────────────────────────────────────
    print("\n[2] Getting running instances...")
    out, _ = run(c, "PGPASSWORD=\"CB_pg_S3cur3_2024!\" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -t -A -F'|' -c \"SELECT subdomain, odoo_port FROM instances WHERE status='RUNNING';\"")

    instances = []
    for line in out.strip().split('\n'):
        parts = line.strip().split('|')
        if len(parts) == 2 and parts[0].strip():
            instances.append((parts[0].strip(), int(parts[1].strip())))
    print(f"  Instances: {instances}")

    # ── 3. Issue LE cert + write nginx for each ──────────────────────────────
    run(c, "mkdir -p /etc/nginx/sites-available/instances")

    for sub, port in instances:
        domain = sub + ".odoo.clickbulid.com"
        print(f"\n[3] Processing {domain}...")

        # Check existing cert
        out, _ = run(c, "test -f /etc/letsencrypt/live/" + domain + "/fullchain.pem && echo EXISTS || echo MISSING")

        if "EXISTS" in out:
            print(f"  Cert already exists")
        else:
            print(f"  Requesting Let's Encrypt cert...")
            out, err = run(c,
                "certbot certonly --webroot -w /var/www/html "
                "-d " + domain + " "
                "--non-interactive --agree-tos "
                "-m " + EMAIL + " 2>&1",
                timeout=90
            )
            if "Successfully" in out or "Certificate not yet due" in out or "fullchain.pem" in out:
                print("  LE cert: SUCCESS")
            elif "error" in out.lower() or "Error" in out:
                print(f"  LE cert failed: {out[-300:]}")
                # Use self-signed as fallback
                run(c, "mkdir -p /etc/letsencrypt/live/" + domain)
                run(c, "cp /etc/ssl/cb-wildcard.crt /etc/letsencrypt/live/" + domain + "/fullchain.pem 2>/dev/null || true")
                run(c, "cp /etc/ssl/cb-wildcard.key /etc/letsencrypt/live/" + domain + "/privkey.pem 2>/dev/null || true")
                print("  Using self-signed cert as fallback")

        # Write HTTPS nginx config
        conf_content = nginx_https_conf(sub)
        conf_path = "/etc/nginx/sites-available/instances/" + sub + ".conf"
        upload(c, conf_path, conf_content)
        run(c, "ln -sf " + conf_path + " /etc/nginx/sites-enabled/" + sub + ".conf 2>/dev/null; echo linked")

    # ── 4. Remove wildcard self-signed block ─────────────────────────────────
    run(c, "rm -f /etc/nginx/sites-enabled/odoo-wildcard-https 2>/dev/null; echo ok")

    # ── 5. Test + reload nginx ────────────────────────────────────────────────
    print("\n[4] Nginx test + reload...")
    out, _ = run(c, "nginx -t 2>&1")
    if "successful" in out:
        run(c, "systemctl reload nginx")
        print("  Nginx reloaded!")
    else:
        print(f"  Error: {out}")
        # Show problematic config
        run(c, "nginx -t 2>&1")

    # ── 6. Patch provisioning.py ─────────────────────────────────────────────
    print("\n[5] Patching provisioning.py for auto-SSL...")
    helper_code = provisioning_helper()
    upload(c, '/tmp/ssl_helper.py', helper_code)

    patch = (
        "python3 -c \""
        "path='/opt/clickbuild/backend/app/services/provisioning.py';"
        "helper=open('/tmp/ssl_helper.py').read();"
        "f=open(path);content=f.read();f.close();"
        "if '_issue_ssl_cert' not in content:"
        "    lines=content.split('\\n');"
        "    last=0;"
        "    [setattr(l,'_',(last:=i)) or None for i,l in enumerate(lines) if l.startswith('import ') or l.startswith('from ')];"
        "    lines.insert(last+1, helper);"
        "    content='\\n'.join(lines);"
        "    f=open(path,'w');f.write(content);f.close();"
        "    print('provisioning.py: SSL helper added');"
        "else:"
        "    print('provisioning.py: already patched')"
        "\""
    )
    run(c, patch, timeout=30)

    # ── 7. Certbot renew hook ────────────────────────────────────────────────
    upload(c, '/etc/letsencrypt/renewal-hooks/post/reload-nginx.sh',
           "#!/bin/bash\nsystemctl reload nginx\n")
    run(c, "chmod +x /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh")

    # ── 8. Restart backend ───────────────────────────────────────────────────
    run(c, "systemctl restart clickbuild-api")
    time.sleep(4)

    # ── 9. Final verification ────────────────────────────────────────────────
    print("\n[6] Final verification...")
    time.sleep(2)
    for sub, _ in instances:
        for proto in ["http", "https"]:
            flag = "-k " if proto == "https" else ""
            out, _ = run(c, "curl " + flag + "-s -o /dev/null -w '%{http_code}' " + proto + "://" + sub + ".odoo.clickbulid.com/web/login 2>/dev/null")
            icon = "OK" if out in ["200","303","301","302"] else "FAIL"
            print(f"  [{icon}] {proto}://{sub}.odoo.clickbulid.com  -> {out}")

    run(c, "certbot certificates 2>&1 | grep -E 'Found|Domains|Expiry|VALID' | head -20")

    print("\n" + "="*60)
    print("DONE")
    print("="*60)
    for sub, _ in instances:
        print(f"  https://{sub}.odoo.clickbulid.com  <- open this in browser")
    print()
    print("If browser still blocks (old HSTS cache):")
    print("  Firefox -> Settings -> Privacy -> Clear Data")
    print("  Check 'Cached Web Content' -> Clear")
    print("  Then try again")
    print("="*60)

    c.close()

if __name__ == "__main__":
    main()
