# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_product_flow = fields.Selection(
        related='product_template_id.x_product_flow',
        string='Product Flow',
        store=False,
        readonly=True,
    )
    x_aantal_platen = fields.Float(
        string='Aantal Platen',
        digits='Product Unit of Measure',
        help='Physical number of sheets. Technical qty = value × m² per plaat.',
    )
    x_aantal_stuks = fields.Float(
        string='Aantal Stuks',
        digits='Product Unit of Measure',
        help='Physical number of pieces. Technical qty = value × lm per stuk.',
    )
    x_aantal_rollen = fields.Float(
        string='Aantal Rollen',
        digits='Product Unit of Measure',
        help='Physical number of rolls. Technical qty = value × m² per rol.',
    )
    x_aantal_pakken = fields.Float(
        string='Aantal Pakken',
        digits='Product Unit of Measure',
        help='Physical number of packs. Technical qty = value × m² per pak.',
    )

    @api.onchange(
        'x_aantal_platen',
        'x_aantal_stuks',
        'x_aantal_rollen',
        'x_aantal_pakken',
        'product_id',
    )
    def _onchange_physical_quantity(self):
        """Backend UI: recalculate product_uom_qty from the active physical field."""
        for line in self:
            if not line.product_id:
                continue
            flow = line.x_product_flow
            technical = line.product_id._get_active_technical_value()
            if flow == 'Sheet':
                physical = line.x_aantal_platen or 0.0
            elif flow == 'Piece':
                physical = line.x_aantal_stuks or 0.0
            elif flow == 'Roll':
                physical = line.x_aantal_rollen or 0.0
            elif flow == 'Pack':
                physical = line.x_aantal_pakken or 0.0
            else:
                continue
            line.product_uom_qty = physical * technical

    def _get_physical_quantity(self):
        """Physical unit count for this line (website display & cart badge)."""
        self.ensure_one()
        flow = self.x_product_flow
        if not flow:
            return self.product_uom_qty
        if flow == 'Sheet':
            physical = self.x_aantal_platen or 0.0
        elif flow == 'Piece':
            physical = self.x_aantal_stuks or 0.0
        elif flow == 'Roll':
            physical = self.x_aantal_rollen or 0.0
        elif flow == 'Pack':
            physical = self.x_aantal_pakken or 0.0
        else:
            return self.product_uom_qty
        # Fallback if physical fields empty but technical qty exists
        if not physical and self.product_uom_qty and self.product_id:
            tech = self.product_id._get_active_technical_value() or 1.0
            physical = self.product_uom_qty / tech if tech else self.product_uom_qty
        return physical

    def _get_displayed_quantity(self):
        """Website cart/checkout: show physical units when product flow is set."""
        self.ensure_one()
        if self.x_product_flow:
            physical = self._get_physical_quantity()
            rounded = round(
                physical,
                self.env['decimal.precision'].precision_get('Product Unit'),
            )
            return int(rounded) if int(rounded) == rounded else rounded
        return super()._get_displayed_quantity()

    def _set_physical_units(self, physical):
        """Write physical quantity onto the correct custom field for this flow."""
        self.ensure_one()
        flow = self.product_id.product_tmpl_id.x_product_flow
        vals = {
            'x_aantal_platen': 0.0,
            'x_aantal_stuks': 0.0,
            'x_aantal_rollen': 0.0,
            'x_aantal_pakken': 0.0,
        }
        if flow == 'Sheet':
            vals['x_aantal_platen'] = physical
        elif flow == 'Piece':
            vals['x_aantal_stuks'] = physical
        elif flow == 'Roll':
            vals['x_aantal_rollen'] = physical
        elif flow == 'Pack':
            vals['x_aantal_pakken'] = physical
        self.write(vals)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _compute_cart_info(self):
        """Header cart badge: sum physical units for flow products."""
        super()._compute_cart_info()
        for order in self:
            total = 0.0
            for line in order.website_order_line:
                if line.product_id and line.product_id.product_tmpl_id.x_product_flow:
                    total += line._get_physical_quantity() or 0.0
                else:
                    total += line.product_uom_qty or 0.0
            order.cart_quantity = int(round(total))

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        """Website add-to-cart: treat quantity as physical, store technical."""
        product = self.env['product.product'].browse(product_id)
        technical = product._get_active_technical_value() if product.exists() else 1.0
        flow = product.product_tmpl_id.x_product_flow if product.exists() else False

        physical_qty = quantity or 0.0
        technical_qty = physical_qty * technical if flow else physical_qty

        result = super()._cart_add(
            product_id=product_id,
            quantity=technical_qty,
            uom_id=uom_id,
            **kwargs,
        )

        line_id = result.get('line_id')
        if line_id and flow:
            line = self.env['sale.order.line'].browse(line_id)
            if line.exists():
                physical = (line.product_uom_qty / technical) if technical else physical_qty
                line._set_physical_units(physical)

        if flow and technical:
            result['quantity'] = (result.get('quantity') or 0.0) / technical
            result['added_qty'] = physical_qty

        return result

    def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
        """Website cart +/- : treat quantity as physical, store technical."""
        line = self.order_line.filtered(lambda sol: sol.id == line_id)[:1]
        flow = False
        technical = 1.0
        physical_qty = quantity

        if line and line.product_id:
            flow = line.product_id.product_tmpl_id.x_product_flow
            if flow:
                technical = line.product_id._get_active_technical_value() or 1.0
                physical_qty = quantity or 0.0
                quantity = physical_qty * technical

        result = super()._cart_update_line_quantity(
            line_id=line_id,
            quantity=quantity,
            **kwargs,
        )

        line_id = result.get('line_id')
        if line_id and flow:
            updated = self.env['sale.order.line'].browse(line_id)
            if updated.exists():
                physical = (updated.product_uom_qty / technical) if technical else physical_qty
                updated._set_physical_units(physical)
                result['quantity'] = physical

        return result
