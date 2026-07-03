from odoo import http
from odoo.http import request
import json
from datetime import date

class SaasStatusController(http.Controller):

    @http.route("/saas/status/api", type="http", auth="public", csrf=False)
    def status_api(self, **kw):

        def check_http(url, timeout=5):
            try:
                from urllib import request as ur
                r = ur.urlopen(url, timeout=timeout)
                return r.status < 500
            except:
                return False

        def check_db():
            try:
                request.env.cr.execute("SELECT 1")
                return True
            except:
                return False

        def check_ssl():
            try:
                import ssl, socket
                ctx = ssl.create_default_context()
                conn = ctx.wrap_socket(
                    socket.create_connection(("odoo.clickbulid.com", 443), timeout=5),
                    server_hostname="odoo.clickbulid.com")
                conn.close()
                return True
            except:
                return False

        def check_backup():
            try:
                request.env.cr.execute(
                    "SELECT value FROM ir_config_parameter "
                    "WHERE key='saas.last_backup_date' LIMIT 1")
                row = request.env.cr.fetchone()
                if not row:
                    return False
                return row[0] == date.today().strftime("%Y-%m-%d")
            except:
                return False

        def count_tenants():
            try:
                request.env.cr.execute(
                    "SELECT COUNT(*) FROM saas_tenant "
                    "WHERE active=true AND state NOT IN ('deleted','archived')")
                row = request.env.cr.fetchone()
                return row[0] if row else 0
            except:
                return 0

        result = {
            "web":          True,
            "community":    check_http("http://127.0.0.1:8069/web/health"),
            "enterprise":   check_http("http://odoo_ent:8069/web/health"),
            "db":           check_db(),
            "ssl":          check_ssl(),
            "backup":       check_backup(),
            "tenant_count": count_tenants(),
        }
        headers = [
            ("Content-Type", "application/json"),
            ("Cache-Control", "no-cache, no-store"),
            ("Access-Control-Allow-Origin", "*"),
        ]
        return request.make_response(json.dumps(result), headers=headers)
