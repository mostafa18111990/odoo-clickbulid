from odoo import models, fields, api
import importlib
import json

GATEWAY_CODES = [
    ('paytabs', 'PayTabs'), ('paymob', 'PayMob'), ('stripe', 'Stripe'),
    ('hyperpay', 'HyperPay'), ('myfatoorah', 'MyFatoorah'),
]
GATEWAY_COUNTRIES = [
    ('SA', 'Saudi Arabia'), ('AE', 'UAE'), ('EG', 'Egypt'), ('KW', 'Kuwait'),
    ('QA', 'Qatar'), ('BH', 'Bahrain'), ('OM', 'Oman'), ('JO', 'Jordan'), ('ALL', 'All Countries'),
]


class SaasPaymentGateway(models.Model):
    _name = 'saas.payment.gateway'
    _description = 'Payment Gateway Configuration'
    _order = 'priority asc, name'
    _rec_name = 'name'

    name = fields.Char(string='Gateway Name', required=True)
    code = fields.Selection(selection=GATEWAY_CODES, string='Gateway', required=True, index=True)
    active = fields.Boolean(default=False, string='Enabled')
    priority = fields.Integer(string='Priority', default=10)
    is_sandbox = fields.Boolean(string='Sandbox / Test Mode', default=True)
    supported_country_ids = fields.Many2many('res.country', string='Supported Countries')
    supported_currencies = fields.Char(string='Supported Currencies', default='SAR,AED,EGP,KWD,USD')
    primary_country = fields.Selection(selection=GATEWAY_COUNTRIES, string='Primary Country')
    api_key = fields.Char(string='API Key / Secret Key', groups='saas_core.group_saas_super_admin')
    api_key_2 = fields.Char(string='API Key 2 / Publishable Key', groups='saas_core.group_saas_super_admin')
    profile_id = fields.Char(string='Profile ID / Merchant ID', groups='saas_core.group_saas_super_admin')
    webhook_secret = fields.Char(string='Webhook Secret / HMAC Key', groups='saas_core.group_saas_super_admin')
    extra_config = fields.Text(string='Extra Configuration (JSON)', groups='saas_core.group_saas_super_admin')
    transaction_count = fields.Integer(string='Transactions', compute='_compute_stats')
    success_count = fields.Integer(string='Successful', compute='_compute_stats')
    failed_count = fields.Integer(string='Failed', compute='_compute_stats')

    def _compute_stats(self):
        for rec in self:
            txs = self.env['saas.payment.transaction'].search([('gateway_id', '=', rec.id)])
            rec.transaction_count = len(txs)
            rec.success_count = len(txs.filtered(lambda t: t.status == 'success'))
            rec.failed_count = len(txs.filtered(lambda t: t.status == 'failed'))

    def get_client(self):
        self.ensure_one()
        extra = {}
        if self.extra_config:
            try:
                extra = json.loads(self.extra_config)
            except (ValueError, TypeError):
                pass
        gateway_map = {
            'paytabs': 'odoo.addons.saas_payment.gateways.paytabs_gateway.PayTabsGateway',
            'paymob': 'odoo.addons.saas_payment.gateways.paymob_gateway.PayMobGateway',
            'stripe': 'odoo.addons.saas_payment.gateways.stripe_gateway.StripeGateway',
            'hyperpay': 'odoo.addons.saas_payment.gateways.hyperpay_gateway.HyperPayGateway',
            'myfatoorah': 'odoo.addons.saas_payment.gateways.myfatoorah_gateway.MyFatoorahGateway',
        }
        path = gateway_map.get(self.code)
        if not path:
            raise ValueError(f'No gateway client for code: {self.code}')
        module_path, class_name = path.rsplit('.', 1)
        GatewayClass = getattr(importlib.import_module(module_path), class_name)
        return GatewayClass(api_key=self.api_key or '', api_key_2=self.api_key_2 or '',
                            profile_id=self.profile_id or '', webhook_secret=self.webhook_secret or '',
                            is_sandbox=self.is_sandbox, extra=extra)

    @api.model
    def get_for_tenant(self, tenant, currency='SAR'):
        country = getattr(tenant, 'customer_country', '') or ''
        country_gateway = {'EG': 'paymob', 'SA': 'hyperpay', 'KW': 'myfatoorah', 'AE': 'paytabs',
                           'QA': 'paytabs', 'BH': 'paytabs', 'OM': 'paytabs', 'JO': 'paytabs'}
        preferred = country_gateway.get(country[:2].upper() if country else '', 'stripe')
        gw = self.search([('code', '=', preferred), ('active', '=', True)], limit=1)
        if gw:
            return gw
        return self.search([('active', '=', True)], order='priority asc', limit=1)

    def action_test_connection(self):
        self.ensure_one()
        try:
            self.get_client().test_connection()
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'type': 'success', 'message': f'{self.name}: Connection OK!'}}
        except Exception as e:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'type': 'danger', 'message': f'{self.name}: failed: {e}'}}
