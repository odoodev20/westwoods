# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    x_counted_physical_units = fields.Float(
        string='Counted Physical Units',
        digits='Product Unit of Measure',
        help='Physical units counted during inventory. '
             'inventory_quantity is auto-calculated as physical × technical factor.',
    )

    @api.onchange('x_counted_physical_units', 'product_id')
    def _onchange_counted_physical_units(self):
        """Auto-calculate inventory_quantity from physical count × technical factor."""
        for quant in self:
            if not quant.product_id:
                continue
            technical = quant.product_id._get_active_technical_value()
            physical = quant.x_counted_physical_units or 0.0
            quant.inventory_quantity = physical * technical
