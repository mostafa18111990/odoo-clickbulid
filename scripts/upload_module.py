#!/usr/bin/env python
"""Upload a local addons/<module> directory to the server via SFTP."""
import paramiko
import os
import sys

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"
REMOTE_ADDONS = "/opt/odoo-saas/addons"


def upload(module: str):
    local_base = os.path.join("addons", module)
    if not os.path.isdir(local_base):
        print(f"ERROR: {local_base} not found")
        return 1
    remote_base = f"{REMOTE_ADDONS}/{module}"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = ssh.open_sftp()

    def mkd(p):
        try:
            sftp.mkdir(p)
        except IOError:
            pass

    mkd(remote_base)
    count = 0
    for root, dirs, files in os.walk(local_base):
        rel = os.path.relpath(root, local_base).replace(os.sep, "/")
        rdir = remote_base if rel == "." else f"{remote_base}/{rel}"
        mkd(rdir)
        for fn in files:
            if fn.endswith(".pyc") or "__pycache__" in root:
                continue
            sftp.put(os.path.join(root, fn), f"{rdir}/{fn}")
            count += 1
    print(f"uploaded {count} files to {remote_base}")
    sftp.close()
    ssh.close()
    return 0


if __name__ == "__main__":
    mods = sys.argv[1:] or ["saas_core"]
    for m in mods:
        upload(m)
