import os

from odoo import _
from odoo.exceptions import UserError


MASTER_KEY_ENV = 'SAAS_EXTERNAL_SERVER_MASTER_KEY'
TOKEN_PREFIX = 'fernet:v1:'


class ExternalServerSecretVault:
    """Encrypt external-server credentials with a key kept outside Odoo DB."""

    @staticmethod
    def _fernet():
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise UserError(_('The cryptography Python package is required.')) from exc
        key = (os.environ.get(MASTER_KEY_ENV) or '').strip().encode('ascii', 'ignore')
        if not key:
            raise UserError(_(
                'External-server credential encryption is not configured. '
                'Set %s in the Odoo container environment.', MASTER_KEY_ENV))
        try:
            return Fernet(key)
        except Exception as exc:
            raise UserError(_('%s must contain a valid Fernet key.', MASTER_KEY_ENV)) from exc

    @classmethod
    def encrypt(cls, value):
        if not value:
            return False
        token = cls._fernet().encrypt(value.encode('utf-8')).decode('ascii')
        return TOKEN_PREFIX + token

    @classmethod
    def decrypt(cls, value):
        if not value:
            return ''
        if not value.startswith(TOKEN_PREFIX):
            raise UserError(_('The stored credential is not encrypted. Re-enter it securely.'))
        try:
            return cls._fernet().decrypt(
                value[len(TOKEN_PREFIX):].encode('ascii')).decode('utf-8')
        except Exception as exc:
            raise UserError(_(
                'Unable to decrypt the server credential. Verify the external-server master key.')) from exc
