from odoo import http
from odoo.http import request
from datetime import date, timedelta
import os

class SaasAdminDashboard(http.Controller):

    def _require_admin(self):
        """Return True if current user is internal admin"""
        return request.env.user.has_group("base.group_system")

    @http.route("/saas/admin", type="http", auth="user", website=True)
    def admin_dashboard(self, **kw):
        if not self._require_admin():
            return request.redirect("/odoo")
        env = request.env
        today = date.today()
        thirty_ago = today - timedelta(days=30)

        tenants = env["saas.tenant"].sudo().search([("active","=",True)])
        by_state = {}
        by_edition = {"community":0,"enterprise":0}
        for t in tenants:
            by_state[t.state] = by_state.get(t.state,0)+1
            if t.edition in by_edition:
                by_edition[t.edition]+=1

        new_30d = env["saas.tenant"].sudo().search_count([
            ("create_date",">=",str(thirty_ago)),("active","=",True)])

        # Failed provisions
        req_dir = "/opt/odoo-saas/cert-requests"
        failed = []
        try:
            for f in os.listdir(req_dir):
                if f.endswith(".provision.error"):
                    sub = f.replace(".provision.error","")
                    retry_f = os.path.join(req_dir, sub+".retries")
                    retries = open(retry_f).read().strip() if os.path.exists(retry_f) else "0"
                    mtime = os.path.getmtime(os.path.join(req_dir,f))
                    import time
                    failed.append({"sub":sub,"retries":retries,
                                   "age_min":int((time.time()-mtime)/60)})
        except:
            pass

        # Backup info
        bak_today = os.path.isdir(f"/opt/backups/{today}")
        bak_count = len([d for d in os.listdir("/opt/backups") if d.startswith("2026")]) \
                    if os.path.isdir("/opt/backups") else 0

        # Plans
        plans = env["saas.plan"].sudo().search([("active","=",True)])

        vals = {
            "total_tenants": len(tenants),
            "by_state": by_state,
            "by_edition": by_edition,
            "new_30d": new_30d,
            "failed_provisions": failed,
            "backup_today": bak_today,
            "backup_days": bak_count,
            "plans": plans,
            "trial_tenants": env["saas.tenant"].sudo().search([
                ("state","=","trial"),("active","=",True)], limit=10),
        }
        # Industry breakdown
        request.env.cr.execute(
            "SELECT COALESCE(industry, 'other') as ind, COUNT(*) as cnt FROM saas_tenant "
            "WHERE active=true AND state NOT IN ('deleted','archived') "
            "GROUP BY ind ORDER BY cnt DESC")
        industry_labels = {
            "retail":"تجزئة ومحلات","restaurant":"مطاعم","ecommerce":"تجارة إلكترونية",
            "trading":"استيراد وتصدير","construction":"مقاولات","manufacturing":"تصنيع",
            "services":"خدمات مهنية","healthcare":"صحة","education":"تعليم",
            "real_estate":"عقارات","logistics":"لوجستيك","hospitality":"فنادق",
            "accounting":"محاسبة","agriculture":"زراعة","technology":"تكنولوجيا","other":"أخرى",
        }
        vals["industry_stats"] = [
            {"industry": r[0], "label": industry_labels.get(r[0], r[0]), "count": r[1]}
            for r in request.env.cr.fetchall()
        ]
        return request.render("saas_website.admin_dashboard", vals)
