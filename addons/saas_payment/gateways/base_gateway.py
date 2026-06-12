from abc import ABC, abstractmethod
import logging

_logger = logging.getLogger(__name__)


class BaseGateway(ABC):
    def __init__(self, api_key='', api_key_2='', profile_id='', webhook_secret='',
                 is_sandbox=True, extra=None):
        self.api_key = api_key
        self.api_key_2 = api_key_2
        self.profile_id = profile_id
        self.webhook_secret = webhook_secret
        self.is_sandbox = is_sandbox
        self.extra = extra or {}

    @abstractmethod
    def create_payment(self, amount, currency, order_id, description, customer_name,
                       customer_email, customer_phone, country_code, callback_url,
                       return_url, cancel_url):
        ...

    @abstractmethod
    def verify_payment(self, gateway_ref):
        ...

    @abstractmethod
    def refund(self, gateway_ref, amount, reason=''):
        ...

    @abstractmethod
    def verify_webhook(self, headers, raw_body):
        ...

    @abstractmethod
    def parse_webhook(self, headers, body):
        ...

    def charge_stored(self, gateway_token, amount, currency, order_id, description):
        raise NotImplementedError(f'{self.__class__.__name__} does not support stored payments.')

    def test_connection(self):
        return True

    @property
    def is_available(self):
        return bool(self.api_key) or bool(self.profile_id)

    def _post(self, url, json_data, headers=None):
        import requests
        try:
            resp = requests.post(url, json=json_data, headers=headers or {}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise RuntimeError(f'Gateway timeout: {url}')
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f'Gateway error {e.response.status_code}: {e.response.text[:200]}')

    def _get(self, url, params=None, headers=None):
        import requests
        resp = requests.get(url, params=params or {}, headers=headers or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _estimate_tokens(text):
        return max(1, len(text or '') // 4)
