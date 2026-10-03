# -*- coding: utf-8 -*-
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WestwoodsWebsiteSale(WebsiteSale):
    def _get_additional_shop_values(self, values, **kwargs):
        """Category architecture helpers for SEO and filter context.

        - Attribute/tag filter combinations must not become uncontrolled indexable URLs.
        - Category route already scopes product templates (Odoo core domain).
        """
        values = super()._get_additional_shop_values(values, **kwargs)
        # Active attribute filters or tags → noindex
        if values.get('attrib_set') or kwargs.get('attribute_values') or kwargs.get('tags'):
            values['ww_noindex'] = True
        # Explicit category browsing remains indexable when no filter query is applied
        if values.get('category') and not values.get('attrib_set') and not kwargs.get('tags'):
            values.setdefault('ww_noindex', False)
        return values
