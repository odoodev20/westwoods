# -*- coding: utf-8 -*-
from odoo.addons.website_sale.controllers.product_configurator import (
    WebsiteSaleProductConfiguratorController,
)


class WestwoodsProductConfiguratorController(WebsiteSaleProductConfiguratorController):
    def _get_basic_product_information(self, product_or_template, pricelist, combination, **kwargs):
        """Expose price per physical unit in the Configure dialog.

        website_sale shows: line_total = price × quantity
        For flow products, quantity is physical (rolls), while `price` is per m².
        Scale `price` by the active conversion factor so the dialog shows the
        correct amount (e.g. 1 roll × $750/m² × 3.5 = $2,625).
        """
        values = super()._get_basic_product_information(
            product_or_template, pricelist, combination, **kwargs
        )
        product = product_or_template
        # Prefer the concrete variant for the combination when we only have a template
        if product._name == 'product.template' and combination is not None:
            variant = product._get_variant_for_combination(combination)
            if variant:
                product = variant
        if not product or product._name not in ('product.product', 'product.template'):
            return values

        tmpl = product if product._name == 'product.template' else product.product_tmpl_id
        flow = tmpl.x_product_flow
        if not flow:
            values['westwoods_factor'] = 1.0
            return values

        if product._name == 'product.product':
            factor = product._get_active_technical_value() or 1.0
        else:
            # template fallback: use first variant or template field
            variant = product.product_variant_id
            factor = (
                variant._get_active_technical_value()
                if variant
                else 1.0
            )

        values['westwoods_factor'] = factor
        if factor and factor != 1.0 and values.get('price') is not None:
            values['price'] = float(values['price']) * float(factor)
            if values.get('strikethrough_price'):
                values['strikethrough_price'] = (
                    float(values['strikethrough_price']) * float(factor)
                )
        return values
