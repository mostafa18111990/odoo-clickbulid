import logging
import json
from datetime import datetime
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AlertNotifier:
    """Send alerts for critical errors and recovery actions."""

    # Alert channels
    CHANNELS = ['email', 'log', 'dashboard', 'webhook']

    @staticmethod
    def notify_error(error_code, message, severity='warning', context=None):
        """Notify admins about platform errors."""
        alert = {
            'code': error_code,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }

        try:
            # Log to file
            _logger.warning(json.dumps(alert, ensure_ascii=False))

            # Send to database for admin dashboard
            if request.env:
                request.env['saas.alert'].create({
                    'code': error_code,
                    'message': message,
                    'severity': severity,
                    'details': json.dumps(alert),
                })

            # Send email for critical errors
            if severity == 'critical':
                AlertNotifier._send_email_alert(alert)

            # Send webhook if configured
            AlertNotifier._send_webhook_alert(alert)

        except Exception as e:
            _logger.error(f"Failed to create alert: {e}")

    @staticmethod
    def _send_email_alert(alert):
        """Send email notification to admins."""
        try:
            admin_group = request.env.ref('base.group_system')
            admin_emails = [user.email for user in admin_group.users if user.email]

            if not admin_emails:
                return

            template_values = {
                'code': alert['code'],
                'message': alert['message'],
                'severity': alert['severity'],
                'timestamp': alert['timestamp'],
                'context': json.dumps(alert['context'], ensure_ascii=False, indent=2),
                'action_url': f"/web/database/manager?alert={alert['code']}"
            }

            subject = f"🚨 Alert [{alert['code']}] - {alert['severity'].upper()}"

            body = f"""
            خطأ على المنصة:

            الرمز: {alert['code']}
            الخطورة: {alert['severity']}
            الرسالة: {alert['message']}
            الوقت: {alert['timestamp']}

            السياق:
            {json.dumps(alert['context'], ensure_ascii=False, indent=2)}

            يرجى التحقق من لوحة المعلومات: {template_values['action_url']}
            """

            mail_values = {
                'subject': subject,
                'body_html': body.replace('\n', '<br/>'),
                'email_to': ','.join(admin_emails),
                'auto_delete': False,
            }

            request.env['mail.mail'].create(mail_values).send()
        except Exception as e:
            _logger.error(f"Failed to send alert email: {e}")

    @staticmethod
    def _send_webhook_alert(alert):
        """Send alert to external webhook if configured."""
        try:
            config = request.env['ir.config_parameter'].sudo()
            webhook_url = config.get_param('saas.alert_webhook_url')

            if not webhook_url:
                return

            import requests
            requests.post(
                webhook_url,
                json=alert,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
        except Exception as e:
            _logger.warning(f"Failed to send webhook alert: {e}")

    @staticmethod
    def notify_recovery(action, target, status):
        """Notify about recovery actions (retries, auto-fixes)."""
        message = f"Recovery action: {action} on {target} - Status: {status}"
        _logger.info(message)

        try:
            if request.env:
                request.env['saas.alert'].create({
                    'code': f'RECOVERY_{action.upper()}',
                    'message': message,
                    'severity': 'info',
                    'details': json.dumps({
                        'action': action,
                        'target': target,
                        'status': status,
                        'timestamp': datetime.now().isoformat()
                    }),
                })
        except Exception as e:
            _logger.error(f"Failed to log recovery action: {e}")
