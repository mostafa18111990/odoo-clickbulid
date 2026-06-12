#!/usr/bin/env python3
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c

def run(c, cmd, timeout=60):
    print(f"\n$ {cmd[:100]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err and not out: print(f"[err] {err[:300]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

PATCH_SCRIPT = """
import sys
path = '/opt/clickbuild/backend/app/services/provisioning.py'

with open(path) as f:
    content = f.read()

if '_issue_ssl_cert' in content:
    print('Already patched')
    sys.exit(0)

helper = '''
import subprocess as _ssl_sp
import os as _ssl_os

def _issue_ssl_cert(subdomain):
    import logging
    logger = logging.getLogger(__name__)
    domain = subdomain + '.odoo.clickbulid.com'
    cert_path = '/etc/letsencrypt/live/' + domain + '/fullchain.pem'
    if _ssl_os.path.exists(cert_path):
        _write_instance_nginx(subdomain)
        return True
    try:
        r = _ssl_sp.run(
            ['certbot', 'certonly', '--webroot', '-w', '/var/www/html',
             '-d', domain, '--non-interactive', '--agree-tos',
             '-m', 'mostafahelmy1995@gmail.com', '--quiet'],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            logger.info('SSL cert issued: ' + domain)
            _write_instance_nginx(subdomain)
            return True
        logger.warning('certbot failed: ' + r.stderr[:200])
        return False
    except Exception as e:
        logger.warning('SSL failed: ' + str(e))
        return False


def _write_instance_nginx(subdomain):
    domain = subdomain + '.odoo.clickbulid.com'
    ledir  = '/etc/letsencrypt/live/' + domain
    cdir   = '/etc/nginx/sites-available/instances'
    _ssl_os.makedirs(cdir, exist_ok=True)
    cpath  = cdir + '/' + subdomain + '.conf'
    epath  = '/etc/nginx/sites-enabled/' + subdomain + '.conf'
    cfg = (
        'server {' + chr(10) +
        '    listen 443 ssl http2;' + chr(10) +
        '    server_name ' + domain + ';' + chr(10) +
        '    ssl_certificate     ' + ledir + '/fullchain.pem;' + chr(10) +
        '    ssl_certificate_key ' + ledir + '/privkey.pem;' + chr(10) +
        '    include             /etc/letsencrypt/options-ssl-nginx.conf;' + chr(10) +
        '    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;' + chr(10) +
        '    add_header X-Frame-Options SAMEORIGIN always;' + chr(10) +
        '    client_max_body_size 100M;' + chr(10) +
        '    proxy_read_timeout 300s;' + chr(10) +
        '    location /.well-known/acme-challenge/ { root /var/www/html; }' + chr(10) +
        '    location / {' + chr(10) +
        '        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;' + chr(10) +
        '        proxy_http_version 1.1;' + chr(10) +
        '        proxy_set_header   Host              $host;' + chr(10) +
        '        proxy_set_header   X-Real-IP         $remote_addr;' + chr(10) +
        '        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;' + chr(10) +
        '        proxy_set_header   X-Forwarded-Proto https;' + chr(10) +
        '        proxy_set_header   X-Odoo-Subdomain  ' + subdomain + ';' + chr(10) +
        '        proxy_buffering    off;' + chr(10) +
        '    }' + chr(10) +
        '}' + chr(10)
    )
    with open(cpath, 'w') as f:
        f.write(cfg)
    if not _ssl_os.path.exists(epath):
        _ssl_os.symlink(cpath, epath)
    _ssl_sp.run(['nginx', '-t'], capture_output=True)
    _ssl_sp.run(['systemctl', 'reload', 'nginx'], capture_output=True)
    import logging
    logging.getLogger(__name__).info('HTTPS nginx written for ' + domain)

'''

# Insert helper after last import line
lines = content.split('\\n')
last_import = 0
for i, line in enumerate(lines):
    if line.startswith('import ') or line.startswith('from '):
        last_import = i

lines.insert(last_import + 1, helper)
content = '\\n'.join(lines)

# Add SSL call where instance goes RUNNING
# Find the spot where we set status to RUNNING after health check passes
import re

# Pattern 1: direct status assignment
for pattern in [
    ('instance.status = InstanceStatus.RUNNING', 'instance.status = InstanceStatus.RUNNING\\n        _issue_ssl_cert(instance.subdomain)'),
    ('status = InstanceStatus.RUNNING', 'status = InstanceStatus.RUNNING\\n            _issue_ssl_cert(subdomain)'),
    ("status='RUNNING'", "status='RUNNING'\\n            _issue_ssl_cert(subdomain)"),
]:
    old, new = pattern
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        print('Added SSL call after: ' + old[:50])
        break

with open(path, 'w') as f:
    f.write(content)
print('provisioning.py patched successfully')
"""

def main():
    c = connect()
    upload(c, '/tmp/patch_prov.py', PATCH_SCRIPT)
    run(c, "python3 /tmp/patch_prov.py", timeout=30)
    run(c, "grep -n '_issue_ssl_cert\\|_write_instance_nginx' /opt/clickbuild/backend/app/services/provisioning.py | head -10")
    run(c, "systemctl restart clickbuild-api && sleep 3 && systemctl is-active clickbuild-api")

    # Final state
    print("\n" + "="*60)
    print("FULL SSL STATUS")
    print("="*60)
    run(c, "certbot certificates 2>&1 | grep -E 'Domains|Expiry|VALID'")
    run(c, "ls /etc/nginx/sites-enabled/ | grep -v default")
    c.close()

if __name__ == "__main__":
    main()
