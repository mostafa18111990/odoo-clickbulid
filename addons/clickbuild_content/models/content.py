from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClickBuildWebsiteContentMixin(models.AbstractModel):
    _name = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Website Content Mixin'

    name = fields.Char(required=True, translate=True)
    slug = fields.Char(required=True, index=True)
    summary = fields.Text(translate=True)
    website_id = fields.Many2one(
        'website', required=True, ondelete='cascade',
        default=lambda self: self.env['website'].get_current_website())
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, index=True)
    published = fields.Boolean(default=False, index=True)
    seo_title = fields.Char(translate=True)
    seo_description = fields.Text(translate=True)
    image = fields.Binary(attachment=True)
    image_alt = fields.Char(translate=True)

    @api.constrains('slug')
    def _check_slug(self):
        for record in self:
            slug = (record.slug or '').strip()
            if not slug or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for char in slug):
                raise ValidationError(_('Slug may contain lowercase letters, numbers, and hyphens only.'))


class ClickBuildApplicationGroup(models.Model):
    _name = 'clickbuild.application.group'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Application Group'
    _order = 'sequence, name, id'

    application_ids = fields.One2many('clickbuild.application', 'group_id')

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Application group slug must be unique per website.')


class ClickBuildApplication(models.Model):
    _name = 'clickbuild.application'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Application'
    _order = 'sequence, name, id'

    group_id = fields.Many2one('clickbuild.application.group', ondelete='set null', index=True)
    capabilities = fields.Text(translate=True)
    outcomes = fields.Text(translate=True)
    related_application_ids = fields.Many2many(
        'clickbuild.application', 'clickbuild_application_related_rel',
        'application_id', 'related_id', string='Related Applications')
    industry_ids = fields.Many2many(
        'clickbuild.industry', 'clickbuild_industry_application_rel',
        'application_id', 'industry_id', string='Industries')

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Application slug must be unique per website.')

    def _catalog_dict(self):
        self.ensure_one()
        arabic = self.with_context(lang='ar_001')
        english = self.with_context(lang='en_US')
        return {
            'slug': self.slug,
            'kind': 'app',
            'title_ar': arabic.name,
            'title_en': english.name,
            'summary_ar': arabic.summary or '',
            'summary_en': english.summary or '',
            'capabilities': [line for line in (self.capabilities or '').splitlines() if line.strip()],
            'outcomes': [line for line in (self.outcomes or '').splitlines() if line.strip()],
            'related': self.related_application_ids.mapped('slug'),
        }


class ClickBuildIndustry(models.Model):
    _name = 'clickbuild.industry'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Industry'
    _order = 'sequence, name, id'

    challenge_ids = fields.One2many('clickbuild.industry.challenge', 'industry_id')
    application_ids = fields.Many2many(
        'clickbuild.application', 'clickbuild_industry_application_rel',
        'industry_id', 'application_id', string='Applications')
    demo_template_id = fields.Many2one('saas.demo.template', ondelete='set null', index=True)

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Industry slug must be unique per website.')

    def _catalog_dict(self):
        self.ensure_one()
        arabic = self.with_context(lang='ar_001')
        english = self.with_context(lang='en_US')
        challenges = self.challenge_ids.filtered(lambda line: line.kind == 'challenge').sorted('sequence')
        workflows = self.challenge_ids.filtered(lambda line: line.kind == 'workflow').sorted('sequence')
        return {
            'slug': self.slug,
            'kind': 'industry',
            'title_ar': arabic.name,
            'title_en': english.name,
            'summary_ar': arabic.summary or '',
            'summary_en': english.summary or '',
            'challenges': challenges.mapped('name'),
            'operations': workflows.mapped('name'),
            'related': self.application_ids.mapped('slug'),
        }


class ClickBuildIndustryChallenge(models.Model):
    _name = 'clickbuild.industry.challenge'
    _description = 'ClickBuild Industry Challenge or Workflow'
    _order = 'sequence, id'

    industry_id = fields.Many2one('clickbuild.industry', required=True, ondelete='cascade', index=True)
    kind = fields.Selection(
        [('challenge', 'Challenge'), ('workflow', 'Connected Workflow')],
        required=True, default='challenge', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)


class ClickBuildService(models.Model):
    _name = 'clickbuild.service'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Service'
    _order = 'sequence, name, id'

    cta_label = fields.Char(translate=True)
    cta_url = fields.Char(default='/contact?type=service')

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Service slug must be unique per website.')


class ClickBuildSolution(models.Model):
    _name = 'clickbuild.solution'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Business Solution'
    _order = 'sequence, name, id'

    application_ids = fields.Many2many('clickbuild.application', string='Applications')
    industry_ids = fields.Many2many('clickbuild.industry', string='Industries')

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Solution slug must be unique per website.')


class ClickBuildIntegration(models.Model):
    _name = 'clickbuild.integration'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Integration'
    _order = 'sequence, name, id'

    status = fields.Selection([
        ('available', 'Available'),
        ('custom', 'Custom Integration'),
        ('planned', 'Under Study'),
        ('unavailable', 'Unavailable'),
    ], default='planned', required=True, index=True)
    application_ids = fields.Many2many('clickbuild.application', string='Applications')
    industry_ids = fields.Many2many('clickbuild.industry', string='Industries')
    evidence_note = fields.Text(help='Internal evidence supporting the public status. Do not store secrets.')

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Integration slug must be unique per website.')


class ClickBuildFaq(models.Model):
    _name = 'clickbuild.faq'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild FAQ'
    _order = 'sequence, name, id'

    answer = fields.Html(required=True, translate=True, sanitize=True)
    category = fields.Selection([
        ('general', 'General'), ('implementation', 'Implementation'),
        ('pricing', 'Pricing'), ('security', 'Security'),
        ('technical', 'Technical'), ('industry', 'Industry'),
    ], default='general', required=True, index=True)

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'FAQ slug must be unique per website.')


class ClickBuildContentBlock(models.Model):
    _name = 'clickbuild.content.block'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Reusable Content Block'
    _order = 'sequence, name, id'

    body = fields.Html(translate=True, sanitize=True)
    block_type = fields.Selection([
        ('text', 'Text'), ('trust', 'Trust'), ('process', 'Process'),
        ('comparison', 'Comparison'), ('notice', 'Notice'),
    ], default='text', required=True, index=True)

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Content block slug must be unique per website.')


class ClickBuildCta(models.Model):
    _name = 'clickbuild.cta'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Call to Action'
    _order = 'sequence, name, id'

    label = fields.Char(required=True, translate=True)
    url = fields.Char(required=True)
    style = fields.Selection([
        ('primary', 'Primary'), ('secondary', 'Secondary'),
        ('outline', 'Outline'), ('link', 'Link'),
    ], default='primary', required=True)

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'CTA slug must be unique per website.')


class ClickBuildMedia(models.Model):
    _name = 'clickbuild.media'
    _inherit = 'clickbuild.website.content.mixin'
    _description = 'ClickBuild Media Asset'
    _order = 'sequence, name, id'

    media_type = fields.Selection([
        ('image', 'Image'), ('video', 'Video'), ('document', 'Document')],
        default='image', required=True, index=True)
    file = fields.Binary(attachment=True)
    filename = fields.Char()
    external_url = fields.Char()
    caption = fields.Text(translate=True)

    _website_slug_unique = models.Constraint(
        'UNIQUE(website_id, slug)', 'Media slug must be unique per website.')

    @api.constrains('file', 'external_url')
    def _check_media_source(self):
        for record in self:
            if record.published and not (record.file or record.external_url or record.image):
                raise ValidationError(_('Published media requires an uploaded file, image, or external URL.'))
