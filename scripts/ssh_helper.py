#!/usr/bin/env python
"""SSH Helper - ينفذ أوامر على السيرفر ويطبع النتيجة"""
import paramiko
import sys
import time

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def run(commands, timeout=300):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)

    if isinstance(commands, str):
        commands = [commands]

    for cmd in commands:
        print(f"\n{'='*60}")
        print(f"$ {cmd}")
        print('='*60)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)

        # طباعة الـ output أثناء التنفيذ
        while not stdout.channel.exit_status_ready():
            if stdout.channel.recv_ready():
                data = stdout.channel.recv(1024).decode('utf-8', errors='replace')
                print(data, end='', flush=True)
            time.sleep(0.1)

        # باقي الـ output
        remaining = stdout.read().decode('utf-8', errors='replace')
        if remaining:
            print(remaining, end='')

        err = stderr.read().decode('utf-8', errors='replace')
        if err:
            print(f"[STDERR] {err}", file=sys.stderr)

        exit_code = stdout.channel.recv_exit_status()
        print(f"\n[exit code: {exit_code}]")

    client.close()

def run_interactive(command, timeout=600):
    """تشغيل أمر طويل مع output مباشر"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)

    chan = client.get_transport().open_session()
    chan.get_pty()
    chan.exec_command(command)

    start = time.time()
    while not chan.exit_status_ready():
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            print(data, end='', flush=True)
        if time.time() - start > timeout:
            print("\n[TIMEOUT]")
            break
        time.sleep(0.1)

    remaining = chan.recv(65535).decode('utf-8', errors='replace')
    if remaining:
        print(remaining, end='')

    client.close()
    return chan.recv_exit_status()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(" ".join(sys.argv[1:]))
    else:
        run(["uname -a", "cat /etc/os-release", "df -h", "free -h", "nproc"])
