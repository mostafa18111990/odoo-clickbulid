from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaasWebsiteBanner(models.Model):
    _name = 'saas.website.banner'
    _description = 'Website Marketing Banner'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    title = fields.Char(required=True)
    title_ar = fields.Char(string='Arabic Title', required=True)
    subtitle = fields.Text(required=True)
    subtitle_ar = fields.Text(string='Arabic Subtitle', required=True)
    eyebrow = fields.Char()
    eyebrow_ar = fields.Char(string='Arabic Eyebrow')
    image_desktop = fields.Binary(attachment=True)
    image_mobile = fields.Binary(attachment=True)
    image_path = fields.Char(help='Fallback static image path used when no desktop image is uploaded.')
    mobile_image_path = fields.Char(help='Fallback static mobile image path.')
    visual_style = fields.Selection(
        [
            ('operations', 'Business operations'),
            ('enterprise', 'Enterprise platform'),
            ('industries', 'Industry applications'),
        ],
        required=True,
        default='operations',
        help='Built-in product visual shown when no banner image is uploaded.',
    )
    cta_label = fields.Char(required=True, default='Learn more')
    cta_label_ar = fields.Char(string='Arabic CTA Label', required=True, default='اعرف المزيد')
    cta_url = fields.Char(required=True, default='/get-started')
    secondary_label = fields.Char()
    secondary_label_ar = fields.Char(string='Arabic Secondary Label')
    secondary_url = fields.Char()
    text_theme = fields.Selection(
        [('light', 'Light text'), ('dark', 'Dark text')],
        required=True,
        default='light',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    date_start = fields.Datetime()
    date_end = fields.Datetime()
    website_id = fields.Many2one('website', ondelete='cascade')

    @api.constrains('cta_url', 'secondary_url', 'image_path', 'mobile_image_path')
    def _check_safe_urls(self):
        for banner in self:
            for value in (
                banner.cta_url,
                banner.secondary_url,
                banner.image_path,
                banner.mobile_image_path,
            ):
                if not value:
                    continue
                parsed = urlparse(value)
                if parsed.scheme and parsed.scheme not in ('http', 'https'):
                    raise ValidationError('Banner URLs must be relative paths or HTTP(S) URLs.')
                if not parsed.scheme and not value.startswith('/'):
                    raise ValidationError('Relative banner URLs must start with /.')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for banner in self:
            if banner.date_start and banner.date_end and banner.date_end <= banner.date_start:
                raise ValidationError('The end date must be later than the start date.')

    @api.model
    def get_published_banners(self):
        now = fields.Datetime.now()
        website = self.env['website'].get_current_website()
        return self.sudo().search([
            ('active', '=', True),
            ('website_id', 'in', [False, website.id]),
            '|', ('date_start', '=', False), ('date_start', '<=', now),
            '|', ('date_end', '=', False), ('date_end', '>=', now),
        ])
