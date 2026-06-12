import logging

_logger = logging.getLogger(__name__)

COUNTRY_DEFAULT_RATES = {'SA': 15.0, 'AE': 5.0, 'EG': 14.0, 'KW': 0.0,
                         'QA': 0.0, 'BH': 10.0, 'OM': 5.0, 'JO': 16.0}


class TaxService:
    def __init__(self, env):
        self.env = env

    def get_tax_for_tenant(self, tenant, line_type='all'):
        country = getattr(tenant, 'customer_country', None) or ''
        country_map = {'Saudi Arabia': 'SA', 'UAE': 'AE', 'Egypt': 'EG', 'Kuwait': 'KW',
                       'Qatar': 'QA', 'Bahrain': 'BH', 'Oman': 'OM', 'Jordan': 'JO'}
        country_code = country_map.get(country, country)
        return self.env['saas.tax.rate'].get_for_country(country_code, line_type)

    def calculate_tax(self, base_amount, tenant, line_type='all'):
        tax_rate = self.get_tax_for_tenant(tenant, line_type)
        if not tax_rate:
            country = getattr(tenant, 'customer_country', '') or ''
            rate_pct = COUNTRY_DEFAULT_RATES.get(country[:2].upper(), 0.0)
            tax_amount = round(base_amount * rate_pct / 100, 2)
            return {'tax_rate': None, 'rate_pct': rate_pct, 'base_amount': base_amount,
                    'tax_amount': tax_amount, 'total': round(base_amount + tax_amount, 2)}
        tax_amount = tax_rate.calculate(base_amount)
        return {'tax_rate': tax_rate, 'rate_pct': tax_rate.rate, 'base_amount': base_amount,
                'tax_amount': tax_amount, 'total': round(base_amount + tax_amount, 2)}

    def get_invoice_tax_label(self, tenant):
        tax = self.get_tax_for_tenant(tenant)
        if tax:
            return (f'{tax.invoice_label} ({tax.rate}%)', f'{tax.invoice_label_ar} ({tax.rate}٪)')
        country = getattr(tenant, 'customer_country', '') or ''
        rate = COUNTRY_DEFAULT_RATES.get(country[:2].upper(), 0.0)
        return (f'VAT ({rate}%)', f'ضريبة القيمة المضافة ({rate}٪)')
