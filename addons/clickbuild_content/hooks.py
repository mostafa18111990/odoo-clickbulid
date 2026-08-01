from odoo.addons.saas_website.controllers.content_catalog import APPLICATIONS, INDUSTRIES, SERVICES


APPLICATION_GROUPS = [
    ('finance', 'Finance', 'المالية'),
    ('sales-service', 'Sales & Customer Service', 'المبيعات وخدمة العملاء'),
    ('operations', 'Operations', 'العمليات'),
    ('hr', 'Human Resources', 'الموارد البشرية'),
    ('commerce-marketing', 'Commerce & Marketing', 'التجارة والتسويق'),
]

APPLICATION_GROUP_MAP = {
    'accounting': 'finance',
    'sales': 'sales-service', 'crm': 'sales-service', 'helpdesk': 'sales-service',
    'purchase': 'operations', 'inventory': 'operations', 'manufacturing': 'operations',
    'maintenance': 'operations', 'quality': 'operations', 'projects': 'operations',
    'employees': 'hr',
    'point-of-sale': 'commerce-marketing', 'ecommerce': 'commerce-marketing',
    'marketing': 'commerce-marketing', 'sign': 'commerce-marketing',
    'subscriptions': 'commerce-marketing',
}

SERVICE_SLUGS = [
    'business-analysis', 'odoo-implementation', 'custom-development',
    'data-migration', 'systems-integration', 'reporting-dashboards',
    'training-change-management', 'support-optimization', 'version-upgrades',
]


def _write_translations(record, english_values, arabic_values):
    record.with_context(lang='en_US').write(english_values)
    arabic = record.env['res.lang'].search([('code', '=', 'ar_001'), ('active', '=', True)], limit=1)
    if arabic:
        record.with_context(lang='ar_001').write(arabic_values)


def _upsert(model, website, slug, values):
    record = model.search([('website_id', '=', website.id), ('slug', '=', slug)], limit=1)
    if not record:
        record = model.create(dict(values, website_id=website.id, slug=slug))
    return record


def post_init_hook(env):
    website = env['website'].search([], order='id', limit=1)
    if not website:
        return

    Group = env['clickbuild.application.group'].sudo()
    groups = {}
    for sequence, (slug, english_name, arabic_name) in enumerate(APPLICATION_GROUPS, start=1):
        group = _upsert(Group, website, slug, {
            'name': english_name, 'sequence': sequence * 10, 'published': True})
        _write_translations(group, {'name': english_name}, {'name': arabic_name})
        groups[slug] = group

    Application = env['clickbuild.application'].sudo()
    applications = {}
    for sequence, item in enumerate(APPLICATIONS.values(), start=1):
        capabilities = '\n'.join(item.get('capabilities') or [])
        outcomes = '\n'.join(item.get('outcomes') or [])
        app = _upsert(Application, website, item['slug'], {
            'name': item['title_en'],
            'summary': item.get('summary_en'),
            'sequence': sequence * 10,
            'published': True,
            'group_id': groups[APPLICATION_GROUP_MAP.get(item['slug'], 'operations')].id,
            'capabilities': capabilities,
            'outcomes': outcomes,
        })
        _write_translations(app,
            {'name': item['title_en'], 'summary': item.get('summary_en')},
            {'name': item['title_ar'], 'summary': item.get('summary_ar')})
        applications[item['slug']] = app

    for item in APPLICATIONS.values():
        related = [applications[slug].id for slug in item.get('related', []) if slug in applications]
        applications[item['slug']].write({'related_application_ids': [(6, 0, related)]})

    Industry = env['clickbuild.industry'].sudo()
    Challenge = env['clickbuild.industry.challenge'].sudo()
    for sequence, item in enumerate(INDUSTRIES.values(), start=1):
        demo_template = env['saas.demo.template'].sudo().search([('sector', '=', item['slug'])], limit=1)
        industry = _upsert(Industry, website, item['slug'], {
            'name': item['title_en'],
            'sequence': sequence * 10,
            'published': True,
            'demo_template_id': demo_template.id,
        })
        _write_translations(industry, {'name': item['title_en']}, {'name': item['title_ar']})
        related = [applications[slug].id for slug in item.get('related', []) if slug in applications]
        industry.write({'application_ids': [(6, 0, related)]})
        if not industry.challenge_ids:
            for kind, lines in [('challenge', item.get('challenges', [])), ('workflow', item.get('operations', []))]:
                for line_sequence, line in enumerate(lines, start=1):
                    Challenge.create({
                        'industry_id': industry.id,
                        'kind': kind,
                        'name': line,
                        'sequence': line_sequence * 10,
                    })

    Service = env['clickbuild.service'].sudo()
    for sequence, ((name, summary), slug) in enumerate(zip(SERVICES, SERVICE_SLUGS), start=1):
        service = _upsert(Service, website, slug, {
            'name': name,
            'summary': summary,
            'sequence': sequence * 10,
            'published': True,
            'cta_label': 'ابدأ تحليل احتياجك',
        })
        _write_translations(service,
            {'name': name, 'summary': summary, 'cta_label': 'Start your discovery'},
            {'name': name, 'summary': summary, 'cta_label': 'ابدأ تحليل احتياجك'})

    env.cr.commit()
