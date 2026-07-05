{
    'name': 'SaaS External Servers',
    'version': '19.0.1.0.0',
    'category': 'SaaS',
    'summary': 'Provision and manage tenants on external (customer-owned) servers over SSH',
    'description': """
Register external servers (a customer's own VPS running the ClickBuild Odoo
docker stack) and provision / suspend / delete tenants on them remotely over
SSH, managed from the same SaaS backend as local tenants.
""",
    'author': 'ClickBuild',
    'website': 'https://clickbuild.com',
    'depends': ['saas_core', 'saas_tenant_manager'],
    'data': [
        'security/ir.model.access.csv',
        'views/saas_external_server_views.xml',
        'views/saas_tenant_deploy_views.xml',
        'wizards/remote_customer_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
