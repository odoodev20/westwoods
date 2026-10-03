# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WestwoodsWebsiteSaleProduct(WebsiteSale):

    def _prepare_product_values(self, product, category, search, **kwargs):
        values = super()._prepare_product_values(product, category, search, **kwargs)
        website = request.website
        # Never expose customer-specific commercial data as public cacheable content
        if website.x_ww_is_b2b or (not request.env.user._is_public()):
            values['ww_private_pricing'] = True
        return values

    @http.route()
    def product(self, product, category=None, search='', **kwargs):
        response = super().product(product, category=category, search=search, **kwargs)
        # Private cache for authenticated / B2B price pages
        try:
            website = request.website
            if website.x_ww_is_b2b or (not request.env.user._is_public()):
                if hasattr(response, 'headers'):
                    response.headers['Cache-Control'] = 'private, no-store'
        except Exception:
            pass
        return response
