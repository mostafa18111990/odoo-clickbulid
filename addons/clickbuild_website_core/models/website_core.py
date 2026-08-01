from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
        """Apply the structure to each website's real (copied) menu tree.

        Odoo copies XML menu records when a website is created, so updating the
        original XML IDs alone does not update the menu rendered by that site.
        """
        specs = {
            '/solutions': ('Solutions', 'الحلول', 10),
            '/industries': ('Industries', 'القطاعات', 15),
            '/demo/request': ('Demos', 'الديموهات', 17),
            '/pricing': ('Pricing', 'الأسعار', 20),
            '/faq': ('Knowledge', 'المعرفة', 30),
            '/contact': ('About Us', 'من نحن', 40),
        }
        children = {
            '/features': ('Overview', 'نظرة عامة', 10),
            '/apps': ('Applications', 'التطبيقات', 20),
            '/services': ('Services', 'الخدمات', 30),
        }
        for website in self.env['website'].sudo().search([]):
            root = self.sudo().search([
                ('website_id', '=', website.id),
                ('parent_id', '=', False),
            ], limit=1)
            if not root:
                continue
            solutions = self.sudo().search([
                ('website_id', '=', website.id),
                ('parent_id', '=', root.id),
                ('url', '=', '/solutions'),
            ], limit=1)
            if not solutions:
                solutions = self.sudo().create({
                    'name': 'Solutions', 'url': '/solutions',
                    'parent_id': root.id, 'website_id': website.id,
                    'sequence': 10,
                })

            for url, (english, arabic, sequence) in specs.items():
                menu = self.sudo().search([
                    ('website_id', '=', website.id),
                    ('parent_id', '=', root.id),
                    ('url', '=', url),
                ], limit=1)
                if not menu:
                    continue
                menu.with_context(lang='en_US').write({
                    'name': english,
                    'url': '/about' if url == '/contact' else url,
                    'sequence': sequence,
                })
                if self.env['res.lang'].search_count([('code', '=', 'ar_001'), ('active', '=', True)]):
                    menu.with_context(lang='ar_001').write({'name': arabic})

            for url, (english, arabic, sequence) in children.items():
                menu = self.sudo().search([
                    ('website_id', '=', website.id),
                    ('url', '=', url),
                ], limit=1)
                if not menu:
                    continue
                menu.with_context(lang='en_US').write({
                    'name': english,
                    'parent_id': solutions.id,
                    'sequence': sequence,
                })
                if self.env['res.lang'].search_count([('code', '=', 'ar_001'), ('active', '=', True)]):
                    menu.with_context(lang='ar_001').write({'name': arabic})
        return True
