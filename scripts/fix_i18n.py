#!/usr/bin/env python
"""Fix next-intl getRequestConfig for v3+ API"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

# Check next-intl version
stdin, stdout, stderr = client.exec_command(
    "cat /opt/clickbuild/frontend/node_modules/next-intl/package.json | grep '\"version\"' | head -1"
)
version = stdout.read().decode('utf-8', errors='replace').strip()
print(f"next-intl version: {version}")

# In next-intl v3+, getRequestConfig uses `requestLocale` (a Promise) not `locale`
new_request_ts = """\
import {getRequestConfig} from 'next-intl/server';

export default getRequestConfig(async ({requestLocale}) => {
  const locale = (await requestLocale) ?? 'ar';
  const validLocale = ['ar', 'en'].includes(locale) ? locale : 'ar';

  const arMessages = (await import('../../messages/ar.json')).default;
  const enMessages = (await import('../../messages/en.json')).default;
  const messages = validLocale === 'ar' ? arMessages : enMessages;

  return { locale: validLocale, messages };
});
"""

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(new_request_ts.encode()), '/opt/clickbuild/frontend/src/i18n/request.ts')
sftp.close()
print("[OK] Fixed src/i18n/request.ts for next-intl v3+")

# Rebuild
print("\nRebuilding frontend...")
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -20"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
code = stdout.channel.recv_exit_status()
print(f"\nBuild exit code: {code}")

if code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | tail -3")
    print(stdout.read().decode('utf-8', errors='replace'))
    time.sleep(2)
    # Quick test
    stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ar/login")
    print(f"Test /ar/login: HTTP {stdout.read().decode().strip()}")
else:
    # Show errors
    stdin, stdout, stderr = client.exec_command(
        "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | grep -E '^Error|error TS|Failed' | head -10"
    )
    print("Errors:", stdout.read().decode('utf-8', errors='replace'))

client.close()
