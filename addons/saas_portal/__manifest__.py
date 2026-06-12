{
    'name': 'SaaS Portal',
    'version': '19.0.1.0.0',
    'category': 'SaaS',
    'summary': 'Customer self-service portal for ClickBuild SaaS',
    'author': 'ClickBuild',
    'website': 'https://clickbuild.com',
    'depends': ['saas_payment', 'portal', 'website'],
    'data': [
        'security/saas_portal_security.xml',
        'security/ir.model.access.csv',
        'views/portal_layout.xml',
        'views/portal_dashboard.xml',
        'views/portal_subscription.xml',
        'views/portal_billing.xml',
        'views/portal_account.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'saas_portal/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
