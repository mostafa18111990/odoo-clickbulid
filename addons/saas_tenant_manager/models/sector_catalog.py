"""Business-sector catalog used when provisioning new tenant databases."""


BUSINESS_SECTORS = {
    'general': {
        'label_en': 'General business',
        'label_ar': 'نشاط عام',
        'common_modules': (),
        'enterprise_modules': (),
    },
    'restaurant': {
        'label_en': 'Restaurants and cafés',
        'label_ar': 'مطاعم ومقاهي',
        'common_modules': (
            'point_of_sale', 'pos_restaurant', 'purchase', 'stock', 'account',
        ),
        'enterprise_modules': (),
    },
    'manufacturing': {
        'label_en': 'Manufacturing',
        'label_ar': 'مصانع وتصنيع',
        'common_modules': (
            'mrp', 'stock', 'purchase', 'sale_management', 'maintenance', 'account',
        ),
        'enterprise_modules': ('quality',),
    },
    'retail': {
        'label_en': 'Retail and shops',
        'label_ar': 'تجزئة ومتاجر',
        'common_modules': (
            'point_of_sale', 'stock', 'purchase', 'sale_management', 'account',
        ),
        'enterprise_modules': (),
    },
    'services': {
        'label_en': 'Professional services',
        'label_ar': 'خدمات مهنية',
        'common_modules': (
            'project', 'sale_management', 'hr_timesheet', 'account',
        ),
        'enterprise_modules': ('helpdesk', 'planning'),
    },
}

BUSINESS_SECTOR_SELECTION = [
    (code, definition['label_en'])
    for code, definition in BUSINESS_SECTORS.items()
]


def get_business_sector_options():
    """Return presentation-safe sector metadata for the public signup page."""
    return [
        {
            'code': code,
            'label_en': definition['label_en'],
            'label_ar': definition['label_ar'],
        }
        for code, definition in BUSINESS_SECTORS.items()
    ]


def get_sector_modules(sector, edition='community'):
    """Return the curated, de-duplicated module list for a sector and edition."""
    sector = sector or 'general'
    if sector not in BUSINESS_SECTORS:
        raise ValueError('Unknown business sector: %s' % sector)
    definition = BUSINESS_SECTORS[sector]
    modules = list(definition['common_modules'])
    if edition == 'enterprise':
        modules.extend(definition['enterprise_modules'])
    return list(dict.fromkeys(modules))


def is_valid_business_sector(sector):
    return sector in BUSINESS_SECTORS
