#!/usr/bin/env python
"""Rebuild frontend with correct API URL (IP-based)"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

print("Building frontend with IP-based API URL...")
build_cmd = (
    "cd /opt/clickbuild/frontend && "
    "NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -15"
)
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
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend && sleep 2 && pm2 list")
    print(stdout.read().decode('utf-8', errors='replace'))
    print("Frontend restarted!")

client.close()
