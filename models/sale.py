# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        help='Physical sheets (Plate). Technical qty = sheets × m² per sheet.',
    )
    x_aantal_stuks = fields.Float(
        string='Aantal Stuks',
        digits='Product Unit of Measure',
        help='Physical pieces (Wood or Piece).',
    )
    x_aantal_rollen = fields.Float(
        string='Aantal Rollen',
        digits='Product Unit of Measure',
        help='Physical rolls (Roll). Technical qty = rolls × m² per roll.',
    )
    x_aantal_pakken = fields.Float(
        string='Aantal Pakken (legacy)',
        digits='Product Unit of Measure',
    )

    def _flow_physical_field(self, flow):
        return {
            'Plate': 'x_aantal_platen',
            'Wood': 'x_aantal_stuks',
            'Piece': 'x_aantal_stuks',
            'Roll': 'x_aantal_rollen',
            'Sheet': 'x_aantal_platen',
            'Pack': 'x_aantal_pakken',
        }.get(flow)

    def _ww_get_physical_from_line(self):
        self.ensure_one()
        field_name = self._flow_physical_field(self.x_product_flow)
        if field_name:
            return getattr(self, field_name) or 0.0
        return 0.0

    @api.onchange(
        'x_aantal_platen',
        'x_aantal_stuks',
        'x_aantal_rollen',
        'x_aantal_pakken',
        'product_id',
    )
    def _onchange_physical_quantity(self):
        for line in self:
            if not line.product_id:
                continue
            flow = line.x_product_flow
            field_name = line._flow_physical_field(flow)
            if not field_name:
                continue
            physical = getattr(line, field_name) or 0.0
            product = line.product_id

            if flow and not product._ww_is_orderable():
                return {
                    'warning': {
                        'title': _('Cannot order this product'),
                        'message': product._ww_order_block_reason(),
                    }
                }

            try:
                product._ww_check_pack_quantity(physical)
            except UserError as err:
                return {
                    'warning': {
                        'title': _('Pack Sale'),
                        'message': err.args[0],
                    }
                }

            technical = product._get_active_technical_value()
            if technical <= 0 and flow:
                return {
                    'warning': {
                        'title': _('Missing conversion'),
                        'message': product._ww_order_block_reason(),
                    }
                }
            # Piece flow: technical is always 1.0 → qty unchanged
            line.product_uom_qty = physical * technical

    @api.constrains(
        'x_aantal_platen', 'x_aantal_stuks', 'x_aantal_rollen',
        'x_aantal_pakken', 'product_id', 'product_uom_qty',
    )
    def _constrain_westwoods_physical(self):
        for line in self:
            if not line.product_id or not line.x_product_flow:
                continue
            product = line.product_id
            if not product._ww_is_orderable():
                raise ValidationError(_(
                    'Order line "%(line)s": %(reason)s'
                ) % {
                    'line': line.display_name,
                    'reason': product._ww_order_block_reason(),
                })
            physical = line._ww_get_physical_from_line()
            if not physical and line.product_uom_qty:
                tech = product._get_active_technical_value()
                if tech > 0:
                    physical = line.product_uom_qty / tech
            if physical:
                product._ww_check_pack_quantity(physical)

    def _get_physical_quantity(self):
        self.ensure_one()
        flow = self.x_product_flow
        if not flow:
            return self.product_uom_qty
        field_name = self._flow_physical_field(flow)
        physical = getattr(self, field_name, 0.0) or 0.0 if field_name else 0.0
        if not physical and self.product_uom_qty and self.product_id:
            tech = self.product_id._get_active_technical_value()
            if tech > 0:
                physical = self.product_uom_qty / tech
            else:
                physical = 0.0
        return physical

    def _get_displayed_quantity(self):
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
        self.ensure_one()
        flow = self.product_id.product_tmpl_id.x_product_flow
        vals = {
            'x_aantal_platen': 0.0,
            'x_aantal_stuks': 0.0,
            'x_aantal_rollen': 0.0,
            'x_aantal_pakken': 0.0,
        }
        field_name = self._flow_physical_field(flow)
        if field_name:
            vals[field_name] = physical
        self.write(vals)

    def _ww_report_subtitle(self):
        """Subtitle under SO line description on PDF."""
        self.ensure_one()
        if not self.product_id or not self.x_product_flow:
            return ''
        physical = self._get_physical_quantity()
        return self.product_id._ww_report_subtitle(physical)


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

    def _ww_prepare_cart_quantity(self, product, quantity):
        """Validate and convert website physical qty → technical qty.

        Returns (physical_qty, technical_qty).
        Raises UserError when the product cannot be ordered or pack rules fail.
        """
        flow = product.product_tmpl_id.x_product_flow
        if not flow:
            return quantity or 0.0, quantity or 0.0

        if not product._ww_is_orderable():
            raise UserError(product._ww_order_block_reason())

        physical_qty = quantity or 0.0
        product._ww_check_pack_quantity(physical_qty)

        technical = product._get_active_technical_value()
        if technical <= 0:
            raise UserError(product._ww_order_block_reason())

        # Piece: technical is 1.0 → physical == technical
        return physical_qty, physical_qty * technical

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return super()._cart_add(product_id=product_id, quantity=quantity, uom_id=uom_id, **kwargs)

        flow = product.product_tmpl_id.x_product_flow
        physical_qty, technical_qty = self._ww_prepare_cart_quantity(product, quantity)

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
                technical = product._get_active_technical_value()
                # After merge, derive total physical from technical line qty
                if technical > 0:
                    physical = line.product_uom_qty / technical
                else:
                    physical = physical_qty
                # Re-validate full line physical qty (merged cart lines)
                product._ww_check_pack_quantity(physical)
                line._set_physical_units(physical)

        if flow:
            technical = product._get_active_technical_value()
            if technical > 0:
                result['quantity'] = (result.get('quantity') or 0.0) / technical
            result['added_qty'] = physical_qty

        return result

    def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
        line = self.order_line.filtered(lambda sol: sol.id == line_id)[:1]
        flow = False
        technical = 1.0
        physical_qty = quantity

        if line and line.product_id:
            product = line.product_id
            flow = product.product_tmpl_id.x_product_flow
            if flow:
                physical_qty, technical_qty = self._ww_prepare_cart_quantity(product, quantity)
                technical = product._get_active_technical_value()
                quantity = technical_qty

        result = super()._cart_update_line_quantity(
            line_id=line_id,
            quantity=quantity,
            **kwargs,
        )

        updated_id = result.get('line_id')
        if updated_id and flow:
            updated = self.env['sale.order.line'].browse(updated_id)
            if updated.exists():
                if technical > 0:
                    physical = updated.product_uom_qty / technical
                else:
                    physical = physical_qty
                updated._set_physical_units(physical)
                result['quantity'] = physical

        return result
