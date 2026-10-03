# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    x_ww_volume_threshold_basis = fields.Selection(
        selection=[
            ('none', 'None (standard Odoo rule)'),
            ('physical', 'Physical Units'),
            ('packs', 'Packs'),
        ],
        string='Volume Threshold Basis',
        default='none',
        help='None: use standard min. quantity as-is.\n'
             'Physical Units: threshold is sheets / pieces / rolls; '
             'technical min. quantity is auto-converted.\n'
             'Packs: threshold is full packs; technical min. uses '
             'Units per Pack × conversion.',
    )
    x_ww_threshold_quantity = fields.Float(
        string='Threshold Quantity',
        digits='Product Unit of Measure',
        help='Human-facing threshold (e.g. 25 pieces, 2 packs). '
             'Technical Min. Quantity is maintained automatically for West-Woods rules.',
    )
    x_ww_technical_min_qty = fields.Float(
        string='Technical Min. Quantity (computed)',
        digits='Product Unit of Measure',
        compute='_compute_ww_technical_min_qty',
        help='Read-only view of the technical quantity stored in Min. Quantity '
             'for West-Woods volume rules.',
    )

    @api.depends(
        'x_ww_volume_threshold_basis',
        'x_ww_threshold_quantity',
        'min_quantity',
        'product_tmpl_id',
        'product_id',
    )
    def _compute_ww_technical_min_qty(self):
        for item in self:
            if item.x_ww_volume_threshold_basis and item.x_ww_volume_threshold_basis != 'none':
                item.x_ww_technical_min_qty = item.min_quantity
            else:
                item.x_ww_technical_min_qty = item.min_quantity

    def _ww_resolve_conversion_and_pack(self):
        """Return (factor, units_per_pack, flow) for this rule's product scope.

        Uses variant when applied on a variant; otherwise template defaults.
        """
        self.ensure_one()
        product = self.product_id
        tmpl = self.product_tmpl_id or (product.product_tmpl_id if product else False)
        if not tmpl and not product:
            return 1.0, 0, False

        if product:
            flow = product.product_tmpl_id.x_product_flow
            factor = product._get_active_technical_value() or 0.0
            units = product._get_units_per_pack() or 0
        else:
            flow = tmpl.x_product_flow
            if not flow or flow == 'Piece':
                factor = 1.0
            elif flow == 'Plate':
                factor = tmpl.x_m2_per_plaat or 0.0
            elif flow == 'Wood':
                factor = tmpl.x_lm_per_stuk or 0.0
            elif flow == 'Roll':
                factor = tmpl.x_m2_per_rol or 0.0
            else:
                factor = 0.0
            units = tmpl.x_units_per_pack or 0
        return factor, units, flow

    def _ww_compute_technical_min_quantity(self):
        """Convert human threshold → technical min_quantity."""
        self.ensure_one()
        basis = self.x_ww_volume_threshold_basis or 'none'
        threshold = self.x_ww_threshold_quantity or 0.0
        if basis == 'none' or threshold <= 0:
            return self.min_quantity

        factor, units_per_pack, flow = self._ww_resolve_conversion_and_pack()
        if factor <= 0:
            factor = 1.0  # pricelist rule without product conversion falls back carefully

        if basis == 'physical':
            # Plate/Roll: sheets/rolls × m²; Wood: pieces × lm; Piece: pieces
            return threshold * factor

        if basis == 'packs':
            if units_per_pack <= 0:
                return 0.0
            # packs × units/pack × conversion
            return threshold * units_per_pack * factor

        return self.min_quantity

    def _ww_sync_min_quantity(self):
        """Write auto-computed technical quantity into standard min_quantity."""
        for item in self:
            if not item.x_ww_volume_threshold_basis or item.x_ww_volume_threshold_basis == 'none':
                continue
            technical = item._ww_compute_technical_min_quantity()
            if item.min_quantity != technical:
                # Use update to avoid recursive write loops
                super(ProductPricelistItem, item).write({'min_quantity': technical})

    @api.onchange(
        'x_ww_volume_threshold_basis',
        'x_ww_threshold_quantity',
        'product_id',
        'product_tmpl_id',
    )
    def _onchange_ww_volume_threshold(self):
        for item in self:
            if item.x_ww_volume_threshold_basis and item.x_ww_volume_threshold_basis != 'none':
                item.min_quantity = item._ww_compute_technical_min_quantity()

    @api.model_create_multi
    def create(self, vals_list):
        items = super().create(vals_list)
        items._ww_sync_min_quantity()
        return items

    def write(self, vals):
        res = super().write(vals)
        trigger = {
            'x_ww_volume_threshold_basis',
            'x_ww_threshold_quantity',
            'product_id',
            'product_tmpl_id',
        }
        if trigger & set(vals.keys()):
            self._ww_sync_min_quantity()
        return res

    @api.constrains('x_ww_volume_threshold_basis', 'x_ww_threshold_quantity', 'product_id', 'product_tmpl_id')
    def _check_ww_volume_rule(self):
        for item in self:
            basis = item.x_ww_volume_threshold_basis or 'none'
            if basis == 'none':
                continue
            if (item.x_ww_threshold_quantity or 0) <= 0:
                raise ValidationError(_(
                    'West-Woods volume rule: Threshold Quantity must be greater than zero.'
                ))
            factor, units_per_pack, flow = item._ww_resolve_conversion_and_pack()
            if basis == 'packs' and units_per_pack <= 0:
                raise ValidationError(_(
                    'West-Woods volume rule (Packs): product must have Units per Pack > 0.'
                ))
            if basis == 'physical' and flow and flow != 'Piece' and factor <= 0:
                raise ValidationError(_(
                    'West-Woods volume rule (Physical Units): product is missing a valid conversion factor.'
                ))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        res = super().write(vals)
        pack_fields = {'x_variant_units_per_pack', 'x_variant_m2_per_plaat',
                       'x_variant_lm_per_stuk', 'x_variant_m2_per_rol'}
        if pack_fields & set(vals.keys()):
            self._ww_recompute_related_volume_rules()
        return res

    def _ww_recompute_related_volume_rules(self):
        """When conversion or pack size changes, refresh Pack/Physical volume rules."""
        Item = self.env['product.pricelist.item']
        for product in self:
            items = Item.search([
                ('x_ww_volume_threshold_basis', 'in', ('physical', 'packs')),
                '|',
                ('product_id', '=', product.id),
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ])
            items._ww_sync_min_quantity()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def write(self, vals):
        res = super().write(vals)
        pack_fields = {
            'x_units_per_pack', 'x_m2_per_plaat', 'x_lm_per_stuk', 'x_m2_per_rol',
            'x_product_flow', 'x_pack_sale_mode',
        }
        if pack_fields & set(vals.keys()):
            self._ww_recompute_related_volume_rules()
        return res

    def _ww_recompute_related_volume_rules(self):
        Item = self.env['product.pricelist.item']
        for tmpl in self:
            items = Item.search([
                ('x_ww_volume_threshold_basis', 'in', ('physical', 'packs')),
                '|',
                ('product_tmpl_id', '=', tmpl.id),
                ('product_id.product_tmpl_id', '=', tmpl.id),
            ])
            items._ww_sync_min_quantity()
