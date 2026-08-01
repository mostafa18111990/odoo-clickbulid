HOME_SECTIONS = [
    ('hero', 'Hero', 'الواجهة الرئيسية', 10),
    ('applications', 'Applications', 'التطبيقات', 20),
    ('implementation-journey', 'Implementation Journey', 'رحلة التنفيذ', 30),
    ('industries', 'Industries', 'القطاعات', 40),
    ('pricing', 'Pricing', 'الأسعار', 50),
    ('enterprise', 'Enterprise', 'إنتربرايز', 60),
    ('implementation-method', 'Implementation Method', 'منهجية التنفيذ', 70),
]


def _translated_write(record, english, arabic):
    record.with_context(lang='en_US').write(english)
    if record.env['res.lang'].search_count([('code', '=', 'ar_001'), ('active', '=', True)]):
        record.with_context(lang='ar_001').write(arabic)


def post_init_hook(env):
    website = env['website'].search([], order='id', limit=1)
    if not website:
        return

    Section = env['clickbuild.home.section'].sudo()
    for key, english_name, arabic_name, sequence in HOME_SECTIONS:
        section = Section.search([
            ('website_id', '=', website.id), ('key', '=', key)], limit=1)
        if not section:
            section = Section.create({
                'name': english_name,
                'key': key,
                'website_id': website.id,
                'sequence': sequence,
                'published': True,
            })
        _translated_write(section, {'name': english_name}, {'name': arabic_name})

    menu_specs = [
        ('clickbuild_website_core.menu_solutions', 'Solutions', 'الحلول', 'fa-th-large', False),
        ('clickbuild_website_core.menu_demos', 'Demos', 'الديموهات', 'fa-play-circle', True),
        ('saas_website.menu_features', 'Overview', 'نظرة عامة', 'fa-th-large', False),
        ('saas_website.menu_apps', 'Applications', 'التطبيقات', 'fa-cubes', True),
        ('saas_website.menu_industries', 'Industries', 'القطاعات', 'fa-industry', True),
        ('saas_website.menu_services', 'Services', 'الخدمات', 'fa-briefcase', False),
        ('saas_website.menu_pricing', 'Pricing', 'الأسعار', 'fa-tag', False),
        ('saas_website.menu_faq', 'Knowledge', 'المعرفة', 'fa-book', False),
        ('saas_website.menu_contact', 'About Us', 'من نحن', 'fa-building', False),
    ]
    for xmlid, english_name, arabic_name, icon, featured in menu_specs:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu:
            continue
        menu.sudo().write({
            'clickbuild_icon': icon,
            'clickbuild_featured': featured,
        })
        _translated_write(menu, {'name': english_name}, {'name': arabic_name})

    env.cr.commit()
