import logging
import json
from datetime import datetime
from functools import wraps
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)


class PlatformError(Exception):
    """Custom exception for platform errors with error codes."""
    def __init__(self, code, message, status=500, details=None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
        super().__init__(self.message)


class ErrorHandler:
    """Centralized error handling and recovery."""

    # Error codes and fallback responses
    ERROR_CODES = {
        'TENANT_PROVISION': {'msg': 'تعذر تجهيز منصة الأعمال', 'en': 'Failed to provision tenant'},
        'DB_CONNECTION': {'msg': 'تعذر الاتصال بقاعدة البيانات', 'en': 'Database connection error'},
        'PAYMENT_FAILED': {'msg': 'تعذرت معالجة عملية الدفع', 'en': 'Payment processing failed'},
        'EMAIL_SEND': {'msg': 'تعذر إرسال البريد الإلكتروني', 'en': 'Email delivery failed'},
        'SSL_CERT': {'msg': 'حدث خطأ في شهادة الاتصال الآمن', 'en': 'SSL certificate error'},
        'INVALID_INPUT': {'msg': 'بعض البيانات المدخلة غير صحيحة', 'en': 'Invalid input'},
        'AUTH_FAILED': {'msg': 'تعذرت المصادقة على بيانات الدخول', 'en': 'Authentication failed'},
        'NOT_FOUND': {'msg': 'لم يتم العثور على المورد المطلوب', 'en': 'Resource not found'},
        'RATE_LIMIT': {'msg': 'تجاوزت الحد المسموح من المحاولات', 'en': 'Too many requests'},
        'UNKNOWN': {'msg': 'حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى', 'en': 'Unexpected error'},
    }

    @staticmethod
    def log_error(code, message, exc=None, context=None):
        """Log error to database and file."""
        try:
            log_entry = {
                'code': code,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'context': context or {},
                'exception': str(exc) if exc else None,
                'request_path': request.httprequest.path if hasattr(request, 'httprequest') else None,
                'request_method': request.httprequest.method if hasattr(request, 'httprequest') else None,
            }
            _logger.error(json.dumps(log_entry, ensure_ascii=False, indent=2))

            # Save to database
            if request.env:
                try:
                    request.env['saas.error.log'].create({
                        'code': code,
                        'message': message,
                        'details': json.dumps(log_entry),
                        'severity': 'critical' if code in ['DB_CONNECTION', 'PAYMENT_FAILED'] else 'warning',
                    })
                except Exception as db_err:
                    _logger.error(f"Failed to log error to DB: {db_err}")
        except Exception as e:
            _logger.error(f"Error logging failed: {e}")

    @staticmethod
    def get_graceful_response(code, lang='ar'):
        """Return user-friendly error message based on language."""
        error = ErrorHandler.ERROR_CODES.get(code, ErrorHandler.ERROR_CODES['UNKNOWN'])
        return error['msg'] if str(lang or '').lower().startswith('ar') else error['en']

    @staticmethod
    def retry_db_operation(func, max_retries=3, delay=1):
        """Retry a database operation on failure."""
        import time
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt < max_retries - 1:
                    _logger.warning(f"DB operation failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    @staticmethod
    def handle_request_error(func):
        """Decorator to handle errors in HTTP requests."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except PlatformError as pe:
                ErrorHandler.log_error(pe.code, pe.message, pe, pe.details)
                lang = request.env.lang if hasattr(request, 'env') else 'ar'
                return {
                    'success': False,
                    'error': ErrorHandler.get_graceful_response(pe.code, lang),
                    'code': pe.code,
                    'status': pe.status
                } if http.request_type == 'json' else request.redirect('/error?code=' + pe.code)
            except ValidationError as ve:
                ErrorHandler.log_error('INVALID_INPUT', str(ve), ve)
                lang = request.env.lang if hasattr(request, 'env') else 'ar'
                return {
                    'success': False,
                    'error': ErrorHandler.get_graceful_response('INVALID_INPUT', lang),
                    'code': 'INVALID_INPUT',
                    'status': 400
                } if hasattr(request, 'httprequest') and 'json' in request.httprequest.content_type else request.redirect('/error?code=INVALID_INPUT')
            except AccessError as ae:
                ErrorHandler.log_error('AUTH_FAILED', str(ae), ae)
                return request.redirect('/web/login')
            except Exception as e:
                ErrorHandler.log_error('UNKNOWN', str(e), e, {
                    'func': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                })
                lang = request.env.lang if hasattr(request, 'env') else 'ar'
                return {
                    'success': False,
                    'error': ErrorHandler.get_graceful_response('UNKNOWN', lang),
                    'code': 'UNKNOWN',
                    'status': 500
                } if hasattr(request, 'httprequest') and 'json' in request.httprequest.content_type else request.redirect('/error?code=UNKNOWN')
        return wrapper


class HealthCheck:
    """Platform health monitoring."""

    @staticmethod
    def check_database():
        """Check database connectivity."""
        try:
            request.env.cr.execute("SELECT 1")
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def check_provisioning_queue():
        """Check if provisioning system is working."""
        try:
            pending = request.env['saas.tenant'].search([
                ('state', '=', 'draft'),
                ('create_date', '<', '2024-01-01')  # Stuck tenants
            ])
            return len(pending) == 0, f"Stuck tenants: {len(pending)}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def check_ssl_certificates():
        """Check SSL certificate health."""
        try:
            import subprocess
            result = subprocess.run(['certbot', 'certificates'], capture_output=True, text=True, timeout=10)
            expired = result.stdout.count('EXPIRED')
            return expired == 0, f"Expired certificates: {expired}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_platform_status():
        """Get overall platform health."""
        checks = {
            'database': HealthCheck.check_database(),
            'provisioning_queue': HealthCheck.check_provisioning_queue(),
            'ssl_certificates': HealthCheck.check_ssl_certificates(),
        }

        all_healthy = all(check[0] for check in checks.values())

        return {
            'healthy': all_healthy,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                name: {
                    'ok': result[0],
                    'details': result[1]
                } for name, result in checks.items()
            }
        }
