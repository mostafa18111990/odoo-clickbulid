{
    'name': 'ClickBuild Website Core',
    'version': '19.0.1.1.0',
    'category': 'Website',
    'summary': 'Governed homepage sections and navigation foundation for ClickBuild 3',
    'author': 'شركة كليك بيلد لتقنية المعلومات',
    'website': 'https://odoo.clickbulid.com',
    'depends': ['clickbuild_content', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'data/navigation_data.xml',
        'views/website_core_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'clickbuild_website_core/static/src/css/foundation.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
