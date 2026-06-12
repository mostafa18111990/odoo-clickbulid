#!/usr/bin/env python3
"""Upload the fixed saas_tenant.py directly via SFTP"""
import paramiko, sys, ast
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LOCAL_FILE = r'C:\Users\user\odoo sas\scripts\saas_tenant_fixed.py'
REMOTE_FILE = '/opt/odoo-saas/addons/saas_tenant_manager/models/saas_tenant.py'

# 1. Verify local syntax first
with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
    src = f.read()

try:
    ast.parse(src)
    print('✅ Local syntax OK')
except SyntaxError as e:
    print(f'❌ Syntax error in local file: {e}')
    sys.exit(1)

# 2. Upload via SFTP
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

sftp = ssh.open_sftp()
sftp.put(LOCAL_FILE, REMOTE_FILE)
sftp.close()
print(f'✅ Uploaded to {REMOTE_FILE}')

def run(cmd, timeout=60):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read().decode('utf-8','replace') + e.read().decode('utf-8','replace')).strip()

# 3. Verify remote syntax
result = run(f'python3 -c "import ast; ast.parse(open(\'{REMOTE_FILE}\').read()); print(\'OK\')"')
print(f'Remote syntax check: {result}')

# 4. Restart Odoo
print('\nRestarting Odoo container...')
print(run('docker restart odoo_saas_app'))

import time
print('Waiting 20s for Odoo to start...')
time.sleep(20)

# 5. Check status
status = run('docker ps --format "table {{.Names}}\t{{.Status}}"')
print('\nContainer status:')
print(status)

# 6. Check odoo logs for errors
logs = run('docker logs odoo_saas_app --tail 30 2>&1')
print('\nOdoo logs (last 30 lines):')
print(logs)

ssh.close()
print('\n✅ Done!')
