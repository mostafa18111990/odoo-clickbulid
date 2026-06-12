{
    'name': 'SaaS Tenant Login Helper',
    'version': '19.0.1.0.0',
    'category': 'SaaS',
    'summary': 'Pre-fills login email from URL hash + paste-password banner',
    'description': '''
Tiny helper installed into every tenant database so the customer who just
signed up at clickbulid.com doesn't have to retype their email at /web/login.

What it does
------------
1. If the URL hash contains "login=<email>", fill the login field automatically.
2. Show a friendly banner reminding the user that the password was copied to
   the clipboard by the signup success page — they just need to paste it.

No backend changes, no security tradeoffs: the hash is never sent to the
server, and the password is never embedded in the URL.
    ''',
    'author': 'ClickBuild',
    'website': 'https://clickbuild.com',
    'depends': ['web'],
    'data': [],
    'assets': {
        # Loaded on every page including /web/login (which uses public assets).
        'web.assets_frontend': [
            'saas_tenant_login_helper/static/src/js/login_autofill.js',
            'saas_tenant_login_helper/static/src/css/login_banner.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
