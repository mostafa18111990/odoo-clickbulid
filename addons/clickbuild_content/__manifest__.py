{
    'name': 'ClickBuild Content',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Editable bilingual content catalog for ClickBuild 3',
    'author': 'شركة كليك بيلد لتقنية المعلومات',
    'website': 'https://odoo.clickbulid.com',
    'depends': ['saas_website', 'saas_demo_management', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/content_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
