import json

from markupsafe import Markup

from odoo import models
from odoo.http import request


class Website(models.Model):
    _inherit = "website"

    _CLICKBUILD_SITEMAP_EXCLUSIONS = {
        "/contactus",
        "/error",
        "/get-started/success",
        "/help",
        "/website/info",
    }

    def _enumerate_pages(self, query_string=None, force=False):
        for page in super()._enumerate_pages(query_string=query_string, force=force):
            path = (page.get("loc") or "").split("?", 1)[0]
            normalized = "/" if path == "/" else path.rstrip("/")
            if normalized in self._CLICKBUILD_SITEMAP_EXCLUSIONS:
                continue
            yield page

    def _clickbuild_schema_json(self):
        self.ensure_one()
        base_url = f"https://{request.httprequest.host}".rstrip("/")
        company_name = self.company_id.name or self.name
        payload = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "@id": f"{base_url}/#organization",
                    "name": company_name,
                    "url": f"{base_url}/",
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"{base_url}/web/image/website/{self.id}/logo",
                    },
                    "contactPoint": {
                        "@type": "ContactPoint",
                        "contactType": "sales",
                        "url": f"{base_url}/contact",
                        "availableLanguage": ["Arabic", "English"],
                    },
                },
                {
                    "@type": "WebSite",
                    "@id": f"{base_url}/#website",
                    "url": f"{base_url}/",
                    "name": self.name,
                    "publisher": {"@id": f"{base_url}/#organization"},
                    "inLanguage": ["ar", "en"],
                },
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        # QWeb escapes ordinary strings, which would leave literal &#34; inside
        # script text. Escape HTML-significant characters at JSON level first,
        # then mark the already-safe JSON as markup so crawlers can parse it.
        serialized = (
            serialized.replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )
        return Markup(serialized)
