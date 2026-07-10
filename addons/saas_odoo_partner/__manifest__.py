{
    'name': 'SaaS Odoo Partner Link',
    'version': '19.0.1.0.0',
    'category': 'SaaS',
    'summary': 'Link the platform to your Odoo partner Enterprise subscription',
    'description': """
For ClickBuild operators who are Odoo partners: store your Odoo Enterprise
subscription code once, have every Enterprise tenant registered against it at
provisioning (database.enterprise_code), and see a monthly license
reconciliation of Enterprise seats × wholesale cost you owe Odoo.
""",
    'author': 'ClickBuild',
    'website': 'https://clickbuild.com',
    'depends': ['saas_core', 'saas_tenant_manager'],
    'data': [
        'views/saas_config_views.xml',
        'views/license_reconciliation_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
