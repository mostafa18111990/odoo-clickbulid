{
    'name': 'SaaS User Limit',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Enforce the ClickBuild plan user limit inside the tenant database',
    'description': """
Blocks creating or reactivating internal users beyond the subscription plan
limit. The limit is written by the ClickBuild provisioner into the
`saas.max_users` system parameter (0 or missing = unlimited).
""",
    'author': 'ClickBuild',
    'website': 'https://clickbuild.com',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
