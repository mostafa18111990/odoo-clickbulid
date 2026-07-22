{
    'name': 'SaaS Enterprise Demo Management',
    'version': '19.0.1.0.0',
    'category': 'SaaS',
    'summary': 'Sector demo requests, Telegram approvals, and Enterprise provisioning',
    'author': 'Click Build Information Technology Company',
    'website': 'https://odoo.clickbulid.com',
    'depends': ['saas_website', 'mail', 'base_setup'],
    'data': [
        'security/saas_demo_security.xml',
        'security/ir.model.access.csv',
        'data/saas_demo_sequence.xml',
        'data/saas_demo_template_data.xml',
        'views/saas_demo_request_views.xml',
        'views/saas_demo_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_demo_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'saas_demo_management/static/src/css/demo_request.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

