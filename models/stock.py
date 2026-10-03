# -*- coding: utf-8 -*-
from math import floor

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    x_counted_physical_units = fields.Float(
        string='Counted Physical Units',
        digits='Product Unit of Measure',
        help='Count in physical units (sheets / pieces / rolls). '
             'Inventory quantity (technical) = physical × conversion factor.',
    )
    x_available_packs = fields.Float(
        string='Available Packs',
        compute='_compute_ww_pack_availability',
        digits='Product Unit of Measure',
        help='floor(on-hand physical units / Units per Pack). Not a separate stock product.',
    )
    x_on_hand_physical = fields.Float(
        string='On Hand (Physical)',
        compute='_compute_ww_pack_availability',
        digits='Product Unit of Measure',
        help='On-hand quantity expressed in physical units for the Product Flow.',
    )

    @api.depends('quantity', 'product_id', 'product_id.x_variant_units_per_pack',
                 'product_id.product_tmpl_id.x_units_per_pack',
                 'product_id.product_tmpl_id.x_product_flow')
    def _compute_ww_pack_availability(self):
        for quant in self:
            product = quant.product_id
            if not product or not product.product_tmpl_id.x_product_flow:
                quant.x_on_hand_physical = quant.quantity or 0.0
                quant.x_available_packs = 0.0
                continue
            factor = product._get_active_technical_value() or 0.0
            if factor > 0:
                physical = (quant.quantity or 0.0) / factor
            else:
                physical = 0.0
            quant.x_on_hand_physical = physical
            units = product._get_units_per_pack() or 0
            if units > 0 and physical > 0:
                quant.x_available_packs = float(floor(physical / units))
            else:
                quant.x_available_packs = 0.0

    @api.onchange('x_counted_physical_units', 'product_id')
    def _onchange_counted_physical_units(self):
        """Inventory adjustment: physical count → technical inventory_quantity."""
        for quant in self:
            if not quant.product_id:
                continue
            product = quant.product_id
            flow = product.product_tmpl_id.x_product_flow
            if not flow:
                quant.inventory_quantity = quant.x_counted_physical_units or 0.0
                continue
            technical = product._get_active_technical_value()
            if technical <= 0:
                # Do not invent a 1.0 factor during inventory
                return {
                    'warning': {
                        'title': _('Missing conversion'),
                        'message': product._ww_order_block_reason() or _(
                            'Set a valid conversion factor before counting this product.'
                        ),
                    }
                }
            physical = quant.x_counted_physical_units or 0.0
            quant.inventory_quantity = physical * technical


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_ww_qty_physical = fields.Float(
        string='On Hand (Physical)',
        compute='_compute_ww_stock_physical',
        digits='Product Unit of Measure',
        help='Free/on-hand stock in physical units (sheets, pieces, rolls).',
    )
    x_ww_packs_available = fields.Float(
        string='Packs Available',
        compute='_compute_ww_stock_physical',
        digits='Product Unit of Measure',
        help='Complete packs available = floor(physical on hand / Units per Pack). '
             'Packs are not separate inventory products.',
    )
    x_ww_stock_unit_label = fields.Char(
        string='Stock Unit',
        compute='_compute_ww_stock_physical',
        help='Physical stock unit label for this Product Flow.',
    )

    def _compute_ww_stock_physical(self):
        for product in self:
            flow = product.product_tmpl_id.x_product_flow
            product.x_ww_stock_unit_label = {
                'Plate': 'sheets',
                'Wood': 'pieces',
                'Piece': 'pieces',
                'Roll': 'rolls',
                'Sheet': 'sheets',
            }.get(flow, product.uom_id.name if product.uom_id else '')
            # qty_available is in technical UoM
            qty = product.qty_available or 0.0
            if not flow:
                product.x_ww_qty_physical = qty
                product.x_ww_packs_available = 0.0
                continue
            factor = product._get_active_technical_value() or 0.0
            if factor > 0:
                physical = qty / factor
            else:
                physical = 0.0
            product.x_ww_qty_physical = physical
            units = product._get_units_per_pack() or 0
            if units > 0 and physical > 0:
                product.x_ww_packs_available = float(floor(physical / units))
            else:
                product.x_ww_packs_available = 0.0


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_ww_qty_physical = fields.Float(
        string='On Hand (Physical)',
        compute='_compute_ww_template_stock_physical',
        digits='Product Unit of Measure',
    )
    x_ww_packs_available = fields.Float(
        string='Packs Available',
        compute='_compute_ww_template_stock_physical',
        digits='Product Unit of Measure',
    )

    def _compute_ww_template_stock_physical(self):
        for tmpl in self:
            physical = 0.0
            packs = 0.0
            for variant in tmpl.product_variant_ids:
                physical += variant.x_ww_qty_physical or 0.0
                packs += variant.x_ww_packs_available or 0.0
            tmpl.x_ww_qty_physical = physical
            tmpl.x_ww_packs_available = packs
