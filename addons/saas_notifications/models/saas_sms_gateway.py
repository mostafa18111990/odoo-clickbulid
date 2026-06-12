from odoo import models, fields, api

SMS_PROVIDERS = [('unifonic', 'Unifonic'), ('twilio', 'Twilio'), ('taqnyat', 'Taqnyat')]


class SaasSmsGateway(models.Model):
    _name = 'saas.sms.gateway'
    _description = 'SMS Gateway'
    _order = 'priority'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    provider = fields.Selection(selection=SMS_PROVIDERS, string='Provider', required=True)
    active = fields.Boolean(default=False)
    priority = fields.Integer(default=10)
    is_sandbox = fields.Boolean(string='Test Mode', default=True)
    api_key = fields.Char(string='API Key', groups='saas_core.group_saas_super_admin')
    api_secret = fields.Char(string='API Secret', groups='saas_core.group_saas_super_admin')
    sender_id = fields.Char(string='Sender ID')
    supported_countries = fields.Char(string='Supported Countries', default='SA,AE,KW,QA,BH,OM,EG,JO')

    def send_sms(self, phone, message):
        self.ensure_one()
        if self.provider == 'unifonic':
            return self._send_unifonic(phone, message)
        elif self.provider == 'twilio':
            return self._send_twilio(phone, message)
        elif self.provider == 'taqnyat':
            return self._send_taqnyat(phone, message)
        return {'success': False, 'error': 'Unknown provider'}

    def _send_unifonic(self, phone, message):
        import requests
        try:
            resp = requests.post('https://el.cloud.unifonic.com/rest/SMS/messages',
                data={'AppSid': self.api_key, 'Recipient': phone, 'Body': message,
                      'SenderID': self.sender_id or 'ClickBuild'}, timeout=20)
            data = resp.json()
            success = data.get('success') in (True, 'true', 'True')
            return {'success': success, 'message_id': data.get('data', {}).get('MessageID', ''),
                    'error': None if success else data.get('message')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_twilio(self, phone, message):
        import requests
        try:
            resp = requests.post(
                f'https://api.twilio.com/2010-04-01/Accounts/{self.api_key}/Messages.json',
                data={'To': phone, 'From': self.sender_id, 'Body': message},
                auth=(self.api_key, self.api_secret), timeout=20)
            data = resp.json()
            return {'success': resp.status_code in (200, 201),
                    'message_id': data.get('sid', ''),
                    'error': data.get('message') if resp.status_code >= 400 else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_taqnyat(self, phone, message):
        import requests
        try:
            resp = requests.post('https://api.taqnyat.sa/v1/messages',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'recipients': [phone], 'body': message, 'sender': self.sender_id or 'ClickBuild'},
                timeout=20)
            data = resp.json()
            return {'success': resp.status_code == 201, 'message_id': str(data.get('messageId', '')),
                    'error': data.get('message') if resp.status_code >= 400 else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @api.model
    def get_for_phone(self, phone):
        return self.search([('active', '=', True)], order='priority', limit=1)
