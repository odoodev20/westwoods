# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.addons.website_sale.controllers.cart import Cart


class WestwoodsCart(Cart):
    def _get_cart_notification_information(self, order, added_qty_per_line):
        """Show physical qty in the popup; price = unit × technical qty."""
        info = super()._get_cart_notification_information(order, added_qty_per_line)
        if not info or not info.get('lines'):
            return info

        show_tax = order.website_id.show_line_subtotals_tax_selection == 'tax_included'
        for line_data in info['lines']:
            line = order.order_line.filtered(lambda l: l.id == line_data['id'])[:1]
            if not line or not line.product_id:
                continue
            flow = line.product_id.product_tmpl_id.x_product_flow
            if not flow:
                continue
            factor = line.product_id._get_active_technical_value() or 0.0
            if factor <= 0:
                factor = 1.0
            physical = added_qty_per_line.get(line.id, 0.0) or 0.0
            unit = (
                line.price_reduce_taxinc if show_tax else line.price_reduce_taxexcl
            )
            line_data['quantity'] = physical
            line_data['price_total'] = unit * physical * factor
        return info
