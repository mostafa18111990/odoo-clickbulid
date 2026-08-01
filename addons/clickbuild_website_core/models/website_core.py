from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


MEGA_MENU_EN = '''
<div class="container py-4 cb-mega-shell">
  <div class="row g-3">
    <div class="col-lg-4">
      <div class="cb-mega-heading">Build your solution</div>
      <a class="cb-mega-link" href="/features"><i class="fa fa-compass"></i><span><strong>Platform overview</strong><small>See how one connected ERP supports your operations.</small></span></a>
      <a class="cb-mega-link" href="/apps"><i class="fa fa-cubes"></i><span><strong>Applications</strong><small>Accounting, sales, inventory, HR, manufacturing and more.</small></span></a>
      <a class="cb-mega-link" href="/services"><i class="fa fa-briefcase"></i><span><strong>Implementation services</strong><small>Analysis, setup, migration, training and support.</small></span></a>
    </div>
    <div class="col-lg-4">
      <div class="cb-mega-heading">Explore by business</div>
      <a class="cb-mega-link" href="/industries"><i class="fa fa-industry"></i><span><strong>Industry solutions</strong><small>Practical workflows shaped around your sector.</small></span></a>
      <a class="cb-mega-link" href="/demo/request"><i class="fa fa-play-circle"></i><span><strong>Enterprise demos</strong><small>Request a prepared demo for your business activity.</small></span></a>
      <a class="cb-mega-link" href="/pricing"><i class="fa fa-tag"></i><span><strong>Plans and pricing</strong><small>Review annual plans and Enterprise options.</small></span></a>
    </div>
    <div class="col-lg-4">
      <div class="cb-mega-heading">Company and guidance</div>
      <a class="cb-mega-link" href="/faq"><i class="fa fa-book"></i><span><strong>Knowledge and FAQ</strong><small>Clear answers before choosing and implementing.</small></span></a>
      <a class="cb-mega-link" href="/about"><i class="fa fa-building"></i><span><strong>About us</strong><small>Our experience, approach and commitment to clients.</small></span></a>
      <a class="cb-mega-link cb-mega-featured" href="/contact"><i class="fa fa-comments"></i><span><strong>Talk to an ERP consultant</strong><small>Discuss your current processes and next step.</small></span></a>
    </div>
  </div>
</div>'''

MEGA_MENU_AR = '''
<div class="container py-4 cb-mega-shell">
  <div class="row g-3">
    <div class="col-lg-4">
      <div class="cb-mega-heading">ابنِ الحل المناسب</div>
      <a class="cb-mega-link" href="/features"><i class="fa fa-compass"></i><span><strong>نظرة عامة على المنصة</strong><small>تعرّف على إدارة عملياتك من خلال نظام ERP مترابط.</small></span></a>
      <a class="cb-mega-link" href="/apps"><i class="fa fa-cubes"></i><span><strong>التطبيقات</strong><small>المحاسبة والمبيعات والمخزون والموارد البشرية والتصنيع والمزيد.</small></span></a>
      <a class="cb-mega-link" href="/services"><i class="fa fa-briefcase"></i><span><strong>خدمات التنفيذ</strong><small>التحليل والإعداد ونقل البيانات والتدريب والدعم.</small></span></a>
    </div>
    <div class="col-lg-4">
      <div class="cb-mega-heading">استكشف حسب نشاطك</div>
      <a class="cb-mega-link" href="/industries"><i class="fa fa-industry"></i><span><strong>حلول القطاعات</strong><small>دورات عمل عملية مصممة بما يناسب طبيعة قطاعك.</small></span></a>
      <a class="cb-mega-link" href="/demo/request"><i class="fa fa-play-circle"></i><span><strong>ديموهات Enterprise</strong><small>اطلب تجربة مجهزة حسب نشاط منشأتك.</small></span></a>
      <a class="cb-mega-link" href="/pricing"><i class="fa fa-tag"></i><span><strong>الباقات والأسعار</strong><small>راجع الباقات السنوية وخيارات Enterprise.</small></span></a>
    </div>
    <div class="col-lg-4">
      <div class="cb-mega-heading">الشركة والإرشاد</div>
      <a class="cb-mega-link" href="/faq"><i class="fa fa-book"></i><span><strong>المعرفة والأسئلة الشائعة</strong><small>إجابات واضحة قبل الاختيار والتنفيذ.</small></span></a>
      <a class="cb-mega-link" href="/about"><i class="fa fa-building"></i><span><strong>من نحن</strong><small>خبرتنا ومنهجية عملنا والتزامنا تجاه العملاء.</small></span></a>
      <a class="cb-mega-link cb-mega-featured" href="/contact"><i class="fa fa-comments"></i><span><strong>تحدث مع مستشار ERP</strong><small>ناقش عملياتك الحالية والخطوة المناسبة لمنشأتك.</small></span></a>
    </div>
  </div>
</div>'''

MEGA_MENU_BILINGUAL = (
    '<div class="cb-mega-locale cb-mega-locale-en">' + MEGA_MENU_EN + '</div>'
    '<div class="cb-mega-locale cb-mega-locale-ar">' + MEGA_MENU_AR + '</div>'
)


class ClickBuildHomeSection(models.Model):
    _name = 'clickbuild.home.section'
    _description = 'ClickBuild Homepage Section'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    key = fields.Char(required=True, index=True)
    website_id = fields.Many2one(
        'website', required=True, ondelete='cascade',
        default=lambda self: self.env['website'].get_current_website())
    sequence = fields.Integer(default=10, index=True)
    published = fields.Boolean(default=True, index=True)
    active = fields.Boolean(default=True, index=True)
    internal_note = fields.Text(help='Internal editorial note. It is never rendered publicly.')

    _website_key_unique = models.Constraint(
        'UNIQUE(website_id, key)', 'Homepage section key must be unique per website.')

    @api.constrains('key')
    def _check_key(self):
        allowed = 'abcdefghijklmnopqrstuvwxyz0123456789-_'
        for record in self:
            key = (record.key or '').strip()
            if not key or any(character not in allowed for character in key):
                raise ValidationError(_('Section key may contain lowercase letters, numbers, hyphens, and underscores only.'))

    @api.model
    def get_public_map(self, website=None):
        website = website or self.env['website'].get_current_website()
        records = self.sudo().search([
            ('website_id', '=', website.id),
            ('active', '=', True),
        ])
        return {
            record.key: {
                'published': record.published,
                'sequence': record.sequence,
            }
            for record in records
        }


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    clickbuild_description = fields.Char(translate=True)
    clickbuild_icon = fields.Char(help='Font Awesome class, for example fa-cubes.')
    clickbuild_featured = fields.Boolean(default=False)

    @api.model
    def _clickbuild_sync_navigation(self):
        """Consolidate legacy links into one bilingual Odoo 19 mega menu.

        Existing link records are detached from the rendered root rather than
        deleted, so rollback and editorial recovery remain straightforward.
        """
        legacy_urls = {
            '/features', '/apps', '/services', '/industries', '/demo/request',
            '/pricing', '/faq', '/about', '/contactus',
        }
        has_arabic = bool(self.env['res.lang'].sudo().search_count([
            ('code', '=', 'ar_001'), ('active', '=', True)]))

        for website in self.env['website'].sudo().search([]):
            root = self.sudo().search([
                ('website_id', '=', website.id),
                ('parent_id', '=', False),
            ], order='id', limit=1)
            if not root:
                continue

            root_children = self.sudo().search([
                ('website_id', '=', website.id),
                ('parent_id', '=', root.id),
            ])
            candidates = root_children.filtered(
                lambda menu: menu.with_context(lang='en_US').name == 'Solutions'
                and menu.url in ('#', '/solutions'))
            solutions = candidates.sorted(
                key=lambda menu: (bool(menu.child_id), menu.id), reverse=True)[:1]
            if not solutions:
                solutions = self.sudo().create({
                    'name': 'Solutions',
                    'url': '/solutions',
                    'parent_id': root.id,
                    'website_id': website.id,
                    'sequence': 10,
                })

            # Odoo 19 forbids child records below a mega menu. Preserve all
            # legacy records as detached roots and publish their destinations
            # through the new mega-menu HTML.
            solutions.child_id.sudo().write({'parent_id': False})
            (candidates - solutions).sudo().write({
                'parent_id': False,
                'mega_menu_content': False,
                'mega_menu_classes': False,
            })
            stale_root_links = root_children.filtered(
                lambda menu: menu != solutions and menu.url in legacy_urls)
            stale_root_links.sudo().write({'parent_id': False})

            solutions.with_context(lang='en_US').sudo().write({
                'name': 'Solutions',
                'parent_id': root.id,
                'sequence': 10,
                'mega_menu_content': MEGA_MENU_BILINGUAL,
                'mega_menu_classes': 'cb-mega-menu border-0 shadow-lg',
            })
            if has_arabic:
                solutions.with_context(lang='ar_001').sudo().write({
                    'name': 'الحلول',
                    # Odoo's HTML translation engine translates text nodes by
                    # source hash. Keeping both variants in the same safe HTML
                    # avoids replacing the English source tree on upgrades.
                    'mega_menu_content': MEGA_MENU_BILINGUAL,
                })
        return True
