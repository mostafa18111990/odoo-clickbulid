from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website as WebsiteController


class ClickBuildWebsiteController(WebsiteController):
    """Keep public crawler endpoints consistent behind the reverse proxy."""

    @http.route()
    def robots(self, **kwargs):
        host = request.httprequest.host
        hostname = host.split(":", 1)[0].lower()
        if hostname.startswith("staging."):
            content = "User-agent: *\nDisallow: /\n"
        else:
            response = super().robots(**kwargs)
            data = response.get_data()
            response.set_data(data.replace(f"http://{host}".encode(), f"https://{host}".encode()))
            return response
        return request.make_response(
            content,
            [("Content-Type", "text/plain; charset=utf-8"), ("Cache-Control", "no-store")],
        )

    @http.route()
    def sitemap_xml_index(self, **kwargs):
        response = super().sitemap_xml_index(**kwargs)
        host = request.httprequest.host
        data = response.get_data()
        response.set_data(data.replace(f"http://{host}".encode(), f"https://{host}".encode()))
        return response
