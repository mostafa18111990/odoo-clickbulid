import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SaasDemoTelegram(http.Controller):

    @http.route('/saas/demo/telegram/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, sitemap=False)
    def telegram_webhook(self, **kw):
        params = request.env['ir.config_parameter'].sudo()
        expected = params.get_param('saas_demo.telegram_webhook_secret') or ''
        supplied = request.httprequest.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not expected or supplied != expected:
            return request.make_json_response({'ok': False}, status=403)
        try:
            update = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return request.make_json_response({'ok': False}, status=400)
        callback = update.get('callback_query') or {}
        parts = (callback.get('data') or '').split(':')
        if len(parts) != 4 or parts[0] != 'demo':
            return request.make_json_response({'ok': True})
        action = {'a': 'approve', 'r': 'reject', 'i': 'info'}.get(parts[1])
        if not action or not parts[2].isdigit():
            return request.make_json_response({'ok': True})
        actor_id = str((callback.get('from') or {}).get('id') or '')
        allowed = {item.strip() for item in (
            params.get_param('saas_demo.telegram_allowed_user_ids') or '').split(',') if item.strip()}
        demo = request.env['saas.demo.request'].sudo().browse(int(parts[2])).exists()
        answer = 'تعذر تنفيذ الإجراء'
        if not demo or actor_id not in allowed:
            answer = 'غير مصرح لك بتنفيذ هذا الإجراء'
        elif not demo.verify_callback_signature(action, parts[3]):
            answer = 'انتهت صلاحية الإجراء أو أن توقيعه غير صحيح'
        else:
            try:
                # Serialize competing clicks. Odoo remains the source of truth
                # when two Telegram administrators act at the same moment.
                request.env.cr.execute(
                    'SELECT id FROM saas_demo_request WHERE id = %s FOR UPDATE',
                    [demo.id])
                demo.invalidate_recordset(['state'])
                if demo.state not in ('new', 'pending_review', 'needs_info'):
                    raise UserWarning('already-decided')
                {'approve': demo.action_approve, 'reject': demo.action_reject,
                 'info': demo.action_needs_info}[action]()
                answer = {'approve': 'تمت الموافقة', 'reject': 'تم الرفض',
                          'info': 'تم طلب معلومات إضافية'}[action]
                demo.message_post(body='Telegram decision by user ID %s: %s' % (actor_id, action))
            except UserWarning:
                answer = 'تم اتخاذ قرار سابقًا لهذا الطلب'
            except Exception:
                _logger.exception('Telegram demo callback failed')
                answer = 'فشل التنفيذ؛ راجع سجل Odoo'
        callback_id = callback.get('id')
        if callback_id and demo:
            try:
                demo._telegram_api('answerCallbackQuery', {
                    'callback_query_id': callback_id, 'text': answer, 'show_alert': False})
                message = callback.get('message') or {}
                chat_id, message_id = (message.get('chat') or {}).get('id'), message.get('message_id')
                if chat_id and message_id:
                    demo._telegram_api('editMessageText', {
                        'chat_id': chat_id, 'message_id': message_id,
                        'text': demo._telegram_text() + '\n\nالقرار: ' + answer,
                        'reply_markup': {'inline_keyboard': []}})
            except Exception:
                _logger.warning('Unable to acknowledge Telegram callback', exc_info=True)
        return request.make_json_response({'ok': True})
