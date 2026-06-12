from datetime import timedelta


class BruteForceService:
    def __init__(self, env):
        self.env = env

    def get_policy(self):
        return self.env['saas.password.policy'].sudo().search(
            [('active', '=', True)], limit=1)

    def detect_and_log(self):
        from odoo import fields
        policy = self.get_policy()
        max_attempts = policy.max_failed_attempts if policy else 5
        window = fields.Datetime.now() - timedelta(minutes=15)
        # Group failed attempts by IP within window via SQL
        self.env.cr.execute("""
            SELECT ip_address, COUNT(*) as cnt
            FROM saas_login_attempt
            WHERE success = false AND create_date >= %s
              AND ip_address IS NOT NULL AND ip_address != ''
            GROUP BY ip_address
            HAVING COUNT(*) >= %s
        """, (window, max_attempts))
        events = []
        for ip, cnt in self.env.cr.fetchall():
            existing = self.env['saas.security.event'].sudo().search([
                ('event_type', '=', 'brute_force'),
                ('ip_address', '=', ip),
                ('resolved', '=', False)], limit=1)
            if existing:
                continue
            ev = self.env['saas.security.event'].sudo().create({
                'event_type': 'brute_force', 'severity': 'high',
                'ip_address': ip,
                'description': f'{cnt} failed login attempts from {ip} in last 15 min'})
            events.append(ev)
        return events
