# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_product_flow = fields.Selection(
        selection=[
            ('Sheet', 'Platen (Sheets)'),
            ('Piece', 'Stuks (Pieces)'),
            ('Roll', 'Rollen (Rolls)'),
            ('Pack', 'Pakken (Packs)'),
        ],
        string='Product Flow',
        help='Defines the physical unit type used for this product. '
             'Technical quantity (UoM) is derived from physical units × conversion factor.',
    )
    x_m2_per_plaat = fields.Float(
        string='m² per Plaat (Sheet)',
        digits='Product Unit of Measure',
        help='Technical surface area (m²) represented by one physical sheet. '
             'Used as default when a variant has no override.',
    )
    x_lm_per_stuk = fields.Float(
        string='lm per Stuk (Piece)',
        digits='Product Unit of Measure',
        help='Technical linear meters represented by one physical piece. '
             'Used as default when a variant has no override.',
    )
    x_m2_per_rol = fields.Float(
        string='m² per Rol (Roll)',
        digits='Product Unit of Measure',
        help='Technical surface area (m²) represented by one physical roll. '
             'Used as default when a variant has no override.',
    )
    x_m2_per_pak = fields.Float(
        string='m² per Pak (Pack)',
        digits='Product Unit of Measure',
        help='Technical surface area (m²) represented by one physical pack. '
             'Used as default when a variant has no override.',
    )

    def _get_combination_info(self, combination=False, product_id=False, add_qty=1.0, uom_id=False, **kwargs):
        """Expose WestWoods factor for the *selected* variant on the website."""
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            uom_id=uom_id,
            **kwargs,
        )
        product_id = combination_info.get('product_id')
        product = self.env['product.product'].browse(product_id) if product_id else self.env['product.product']
        if not product and product_id:
            product = self.env['product.product'].sudo().browse(product_id)
        if product and product.exists() and product.product_tmpl_id.x_product_flow:
            flow = product.product_tmpl_id.x_product_flow
            tech = product._get_active_technical_value()
            combination_info.update({
                'westwoods_flow': flow,
                'westwoods_factor': tech,
                'westwoods_unit_label': {
                    'Sheet': 'platen',
                    'Piece': 'stuks',
                    'Roll': 'rollen',
                    'Pack': 'pakken',
                }.get(flow, ''),
                'westwoods_factor_label': {
                    'Sheet': 'm² per plaat',
                    'Piece': 'lm per stuk',
                    'Roll': 'm² per rol',
                    'Pack': 'm² per pak',
                }.get(flow, ''),
                'westwoods_tech_unit': {
                    'Sheet': 'm²',
                    'Piece': 'lm',
                    'Roll': 'm²',
                    'Pack': 'm²',
                }.get(flow, ''),
            })
        else:
            combination_info.update({
                'westwoods_flow': False,
                'westwoods_factor': 1.0,
                'westwoods_unit_label': '',
                'westwoods_factor_label': '',
                'westwoods_tech_unit': '',
            })
        return combination_info


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_product_flow = fields.Selection(
        related='product_tmpl_id.x_product_flow',
        string='Product Flow',
        store=False,
        readonly=True,
    )
    x_variant_m2_per_plaat = fields.Float(
        string='Variant m² per Plaat',
        digits='Product Unit of Measure',
        help='Override for this variant only. Leave 0 to use the template value.',
    )
    x_variant_lm_per_stuk = fields.Float(
        string='Variant lm per Stuk',
        digits='Product Unit of Measure',
        help='Override for this variant only. Leave 0 to use the template value.',
    )
    x_variant_m2_per_rol = fields.Float(
        string='Variant m² per Rol',
        digits='Product Unit of Measure',
        help='Override for this variant only. Leave 0 to use the template value.',
    )
    x_variant_m2_per_pak = fields.Float(
        string='Variant m² per Pak',
        digits='Product Unit of Measure',
        help='Override for this variant only. Leave 0 to use the template value.',
    )

    def _get_active_technical_value(self):
        """Return the conversion factor for the active product flow.

        Priority:
        1. Variant-level factor (if set and > 0)
        2. Template-level factor (if set and > 0)
        3. Safe default of 1.0
        """
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return 1.0

        mapping = {
            'Sheet': ('x_variant_m2_per_plaat', 'x_m2_per_plaat'),
            'Piece': ('x_variant_lm_per_stuk', 'x_lm_per_stuk'),
            'Roll': ('x_variant_m2_per_rol', 'x_m2_per_rol'),
            'Pack': ('x_variant_m2_per_pak', 'x_m2_per_pak'),
        }
        variant_field, template_field = mapping.get(flow, (None, None))
        if not variant_field:
            return 1.0

        variant_val = getattr(self, variant_field, 0.0) or 0.0
        if variant_val > 0.0:
            return variant_val

        template_val = getattr(self.product_tmpl_id, template_field, 0.0) or 0.0
        if template_val > 0.0:
            return template_val

        return 1.0
