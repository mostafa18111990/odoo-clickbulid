"""
Nginx Service - إدارة ملفات Nginx للـ instances تلقائياً
"""
import subprocess
from datetime import datetime
from pathlib import Path

SITES_DIR    = "/etc/nginx/sites-available/instances"
ENABLED_DIR  = "/etc/nginx/sites-enabled"
TEMPLATE     = "/opt/clickbuild/nginx/instance.template"


class NginxService:

    def add_instance_config(
        self,
        subdomain: str,
        port: int,
        longpolling_port: int,
        odoo_version: str
    ):
        with open(TEMPLATE) as f:
            config = f.read()

        config = config.replace("{{SUBDOMAIN}}", subdomain)
        config = config.replace("{{ODOO_PORT}}", str(port))
        config = config.replace("{{LONGPOLLING_PORT}}", str(longpolling_port))
        config = config.replace("{{ODOO_VERSION}}", odoo_version)
        config = config.replace("{{CREATED_AT}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        config_path = Path(SITES_DIR) / f"{subdomain}.conf"
        enabled_path = Path(ENABLED_DIR) / f"{subdomain}.conf"

        config_path.write_text(config)
        if not enabled_path.exists():
            enabled_path.symlink_to(config_path)

        self._reload_nginx()

    def remove_instance_config(self, subdomain: str):
        config_path  = Path(SITES_DIR) / f"{subdomain}.conf"
        enabled_path = Path(ENABLED_DIR) / f"{subdomain}.conf"

        if enabled_path.exists():
            enabled_path.unlink()
        if config_path.exists():
            config_path.unlink()

        self._reload_nginx()

    def _reload_nginx(self):
        test = subprocess.run(["nginx", "-t"], capture_output=True)
        if test.returncode != 0:
            raise RuntimeError(f"Nginx config error: {test.stderr.decode()}")
        subprocess.run(["nginx", "-s", "reload"], check=True)
