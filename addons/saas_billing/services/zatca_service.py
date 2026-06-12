import base64
import hashlib
import logging

_logger = logging.getLogger(__name__)


class ZatcaService:
    @staticmethod
    def generate_qr(seller_name, vat_number, timestamp, total, vat_amount):
        try:
            def _tlv(tag, value):
                encoded = value.encode('utf-8')
                return bytes([tag, len(encoded)]) + encoded
            tlv = b''
            tlv += _tlv(1, seller_name or 'ClickBuild')
            tlv += _tlv(2, vat_number or '300000000000003')
            tlv += _tlv(3, timestamp)
            tlv += _tlv(4, f'{total:.2f}')
            tlv += _tlv(5, f'{vat_amount:.2f}')
            return base64.b64encode(tlv).decode('utf-8')
        except Exception as e:
            _logger.error('ZATCA QR generation failed: %s', e)
            return ''

    @staticmethod
    def generate_invoice_hash(invoice_data):
        try:
            import json
            canonical = json.dumps(invoice_data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        except Exception as e:
            _logger.error('Invoice hash generation failed: %s', e)
            return ''

    @staticmethod
    def validate_vat_number(vat_number):
        if not vat_number:
            return False
        clean = vat_number.strip().replace(' ', '')
        return len(clean) == 15 and clean.isdigit() and clean[0] == '3' and clean[-1] == '3'
