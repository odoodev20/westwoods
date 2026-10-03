# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


PRODUCT_FLOW_SELECTION = [
    ('Plate', 'Plate (Platen / Sheets)'),
    ('Wood', 'Wood (Hout — lm)'),
    ('Piece', 'Piece (Stuks)'),
    ('Roll', 'Roll (Rollen)'),
]

PACK_SALE_MODE_TEMPLATE = [
    ('none', 'None'),
    ('optional', 'Optional'),
    ('required', 'Required'),
]

PACK_SALE_MODE_VARIANT = [
    ('inherit', 'Inherit from template'),
    ('none', 'None'),
    ('optional', 'Optional'),
    ('required', 'Required'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_product_flow = fields.Selection(
        selection=PRODUCT_FLOW_SELECTION,
        string='Product Flow',
        help='Controls physical order unit and technical conversion. '
             'Pack selling is configured separately (Pack Sale), not as a flow.',
    )
    x_m2_per_plaat = fields.Float(
        string='m² per Sheet (Plate)',
        digits=(16, 4),
        help='Default m² per full sheet (Plate). Variant may override.',
    )
    x_lm_per_stuk = fields.Float(
        string='lm per Piece (Wood)',
        digits=(16, 4),
        help='Default linear metres per physical wood piece (Wood). Variant may override.',
    )
    x_m2_per_rol = fields.Float(
        string='m² per Roll',
        digits=(16, 4),
        help='Default m² per full roll (Roll). Variant may override.',
    )
    x_m2_per_pak = fields.Float(
        string='m² per Pack (legacy, unused)',
        digits=(16, 4),
        help='Deprecated. Pack is not a Product Flow.',
    )
    x_pack_sale_mode = fields.Selection(
        selection=PACK_SALE_MODE_TEMPLATE,
        string='Pack Sale Mode',
        default='none',
        help='None: physical units only. Optional: loose or packs. '
             'Required: complete pack multiples only.',
    )
    x_units_per_pack = fields.Integer(
        string='Units per Pack',
        default=0,
        help='Physical units per pack. Required > 0 when Pack Sale is Optional or Required.',
    )

    @api.constrains('x_pack_sale_mode', 'x_units_per_pack')
    def _check_pack_sale_config(self):
        for tmpl in self:
            if tmpl.x_pack_sale_mode in ('optional', 'required') and (tmpl.x_units_per_pack or 0) <= 0:
                raise ValidationError(_(
                    'Product "%(name)s": Pack Sale Mode is %(mode)s but Units per Pack is missing or zero. '
                    'Set Units per Pack > 0, or set Pack Sale Mode to None.'
                ) % {
                    'name': tmpl.display_name,
                    'mode': tmpl.x_pack_sale_mode,
                })

    def _get_combination_info(self, combination=False, product_id=False, add_qty=1.0, uom_id=False, **kwargs):
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            uom_id=uom_id,
            **kwargs,
        )
        product_id = combination_info.get('product_id')
        product = self.env['product.product'].browse(product_id) if product_id else self.env['product.product']
        if product and product.exists() and product.product_tmpl_id.x_product_flow:
            flow = product.product_tmpl_id.x_product_flow
            tech = product._get_active_technical_value()
            orderable = product._ww_is_orderable()
            combination_info.update({
                'westwoods_flow': flow,
                'westwoods_factor': tech if tech > 0 else 0.0,
                'westwoods_unit_label': product._get_physical_unit_label(),
                'westwoods_factor_label': product._get_factor_label(),
                'westwoods_tech_unit': product._get_technical_unit_label(),
                'westwoods_pack_sale_mode': product._get_effective_pack_sale_mode(),
                'westwoods_units_per_pack': product._get_units_per_pack(),
                'westwoods_orderable': orderable,
                'westwoods_block_reason': product._ww_order_block_reason() if not orderable else '',
                'westwoods_use_variant_price': product.x_ww_use_variant_price_override,
                'westwoods_base_price': product._get_ww_effective_base_price(),
            })
            if not orderable:
                combination_info['prevent_zero_price_sale'] = True
        else:
            combination_info.update({
                'westwoods_flow': False,
                'westwoods_factor': 1.0,
                'westwoods_unit_label': '',
                'westwoods_factor_label': '',
                'westwoods_tech_unit': '',
                'westwoods_pack_sale_mode': 'none',
                'westwoods_units_per_pack': 0,
                'westwoods_orderable': True,
                'westwoods_block_reason': '',
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
        string='Variant m² per Sheet',
        digits=(16, 4),
        help='Plate override. Leave 0 to use the template default.',
    )
    x_variant_lm_per_stuk = fields.Float(
        string='Variant lm per Piece',
        digits=(16, 4),
        help='Wood override. Leave 0 to use the template default.',
    )
    x_variant_m2_per_rol = fields.Float(
        string='Variant m² per Roll',
        digits=(16, 4),
        help='Roll override. Leave 0 to use the template default.',
    )
    x_variant_m2_per_pak = fields.Float(
        string='Variant m² per Pack (legacy, unused)',
        digits=(16, 4),
    )
    x_variant_pack_sale_mode = fields.Selection(
        selection=PACK_SALE_MODE_VARIANT,
        string='Pack Sale Mode (Variant)',
        default='inherit',
    )
    x_variant_units_per_pack = fields.Integer(
        string='Units per Pack (Variant)',
        default=0,
        help='Override when > 0. Leave 0 to inherit from template.',
    )

    # --- Phase 3: direct variant base sales price ---
    x_ww_use_variant_price_override = fields.Boolean(
        string='Use Variant Base Price',
        default=False,
        help='When enabled, this variant uses its own base sales price '
             'instead of the template Sales Price. '
             'Zero is a valid price and does NOT mean "inherit".',
    )
    x_ww_variant_base_sale_price = fields.Float(
        string='Variant Base Sales Price',
        digits='Product Price',
        help='Effective base price in the Product Flow pricing unit '
             '(€/m², €/lm, or €/piece). Used only when '
             '"Use Variant Base Price" is enabled. Feeds Odoo pricelist resolution.',
    )

    # -------------------------------------------------------------------------
    # Pricing — central Odoo list_price path
    # -------------------------------------------------------------------------

    def _get_ww_effective_base_price(self):
        """Template list_price, or variant override when explicitly enabled."""
        self.ensure_one()
        if self.x_ww_use_variant_price_override:
            return self.x_ww_variant_base_sale_price or 0.0
        return self.list_price or 0.0

    @api.depends(
        'list_price', 'price_extra',
        'x_ww_use_variant_price_override', 'x_ww_variant_base_sale_price',
    )
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        """Catalog sales price: respect variant base override; no attribute extras when override is on."""
        super()._compute_product_lst_price()
        to_uom = None
        if 'uom' in self.env.context:
            to_uom = self.env['uom.uom'].browse(self.env.context['uom'])
        for product in self:
            if not product.x_ww_use_variant_price_override:
                continue
            # Explicit override: base only (do not add attribute price extras)
            price = product.x_ww_variant_base_sale_price or 0.0
            if to_uom and product.uom_id:
                price = product.uom_id._compute_price(price, to_uom)
            product.lst_price = price

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        """Inject variant base price into the central list_price resolution path.

        Pricelists, cart, website and matrix all use this hook for the product base.
        """
        prices = super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date,
        )
        if price_type != 'list_price':
            return prices

        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        for product in self:
            if not product.x_ww_use_variant_price_override:
                continue
            # Rebuild price from override without attribute extras
            price = product.x_ww_variant_base_sale_price or 0.0
            price_currency = product.currency_id
            if uom:
                price = product.uom_id._compute_price(price, uom)
            if currency:
                price = price_currency._convert(price, currency, company, date)
            prices[product.id] = price
        return prices

    # -------------------------------------------------------------------------
    # Conversion & pack resolution
    # -------------------------------------------------------------------------

    def _get_active_technical_value(self):
        """Return conversion factor, or 0.0 if missing/invalid (no silent 1.0)."""
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return 0.0
        if flow == 'Piece':
            return 1.0

        mapping = {
            'Plate': ('x_variant_m2_per_plaat', 'x_m2_per_plaat'),
            'Wood': ('x_variant_lm_per_stuk', 'x_lm_per_stuk'),
            'Roll': ('x_variant_m2_per_rol', 'x_m2_per_rol'),
            'Sheet': ('x_variant_m2_per_plaat', 'x_m2_per_plaat'),
            'Pack': ('x_variant_m2_per_pak', 'x_m2_per_pak'),
        }
        variant_field, template_field = mapping.get(flow, (None, None))
        if not variant_field:
            return 0.0

        variant_val = getattr(self, variant_field, 0.0) or 0.0
        if variant_val > 0.0:
            return variant_val
        template_val = getattr(self.product_tmpl_id, template_field, 0.0) or 0.0
        if template_val > 0.0:
            return template_val
        return 0.0

    def _get_pack_sale_mode_raw(self):
        self.ensure_one()
        mode = self.x_variant_pack_sale_mode or 'inherit'
        if mode == 'inherit':
            return self.product_tmpl_id.x_pack_sale_mode or 'none'
        return mode

    def _get_units_per_pack(self):
        self.ensure_one()
        if self.x_variant_units_per_pack and self.x_variant_units_per_pack > 0:
            return self.x_variant_units_per_pack
        return self.product_tmpl_id.x_units_per_pack or 0

    def _get_effective_pack_sale_mode(self):
        self.ensure_one()
        mode = self._get_pack_sale_mode_raw()
        if mode in ('optional', 'required') and self._get_units_per_pack() <= 0:
            return 'none'
        return mode

    def _get_pack_sale_mode(self):
        return self._get_effective_pack_sale_mode()

    def _ww_pack_config_error(self):
        self.ensure_one()
        mode = self._get_pack_sale_mode_raw()
        return mode in ('optional', 'required') and self._get_units_per_pack() <= 0

    def _ww_is_orderable(self):
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return True
        if self._get_active_technical_value() <= 0:
            return False
        return True

    def _ww_order_block_reason(self):
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return ''
        if self._get_active_technical_value() <= 0:
            labels = {
                'Plate': _('Missing or invalid m² per sheet (Plate).'),
                'Wood': _('Missing or invalid lm per piece (Wood).'),
                'Roll': _('Missing or invalid m² per roll (Roll).'),
                'Piece': _('Invalid Piece configuration.'),
                'Sheet': _('Missing or invalid m² per sheet.'),
            }
            return labels.get(flow, _('Missing conversion data. This variant cannot be ordered.'))
        return ''

    def _ww_check_pack_quantity(self, physical_qty):
        self.ensure_one()
        mode = self._get_effective_pack_sale_mode()
        units = self._get_units_per_pack()
        if mode != 'required' or units <= 0:
            return
        if not physical_qty:
            return
        qty_int = int(round(physical_qty))
        if abs(physical_qty - qty_int) > 1e-6:
            raise UserError(_(
                'Pack Sale is Required for "%(name)s". '
                'Quantity must be a whole number of physical units '
                '(multiples of %(units)s).'
            ) % {'name': self.display_name, 'units': units})
        if qty_int % units != 0:
            raise UserError(_(
                'Pack Sale is Required for "%(name)s". '
                'Order in complete packs only (%(units)s units per pack). '
                'Requested: %(qty)s.'
            ) % {'name': self.display_name, 'units': units, 'qty': qty_int})

    def _is_add_to_cart_allowed(self):
        allowed = super()._is_add_to_cart_allowed()
        if not allowed:
            return allowed
        for product in self:
            if product.product_tmpl_id.x_product_flow and not product._ww_is_orderable():
                return False
        return True

    def _get_physical_unit_label(self):
        self.ensure_one()
        return {
            'Plate': 'platen',
            'Wood': 'stuks',
            'Piece': 'stuks',
            'Roll': 'rollen',
            'Sheet': 'platen',
            'Pack': 'pakken',
        }.get(self.product_tmpl_id.x_product_flow, '')

    def _get_factor_label(self):
        self.ensure_one()
        return {
            'Plate': 'm² per plaat',
            'Wood': 'lm per stuk',
            'Piece': '',
            'Roll': 'm² per rol',
            'Sheet': 'm² per plaat',
        }.get(self.product_tmpl_id.x_product_flow, '')

    def _get_technical_unit_label(self):
        self.ensure_one()
        return {
            'Plate': 'm²',
            'Wood': 'lm',
            'Piece': 'stuk',
            'Roll': 'm²',
            'Sheet': 'm²',
        }.get(self.product_tmpl_id.x_product_flow, '')


    def _ww_format_physical_qty(self, physical):
        """Format physical quantity for reports (e.g. 6,0)."""
        self.ensure_one()
        if physical is None:
            return ''
        if abs(physical - round(physical)) < 1e-6:
            return '%d' % int(round(physical))
        return ('%.4f' % physical).rstrip('0').rstrip('.')

    def _ww_report_subtitle(self, physical_qty):
        """Report line subtitle: 'Aantal platen: 6,0 | m² per plaat: 3,125'."""
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return ''
        factor = self._get_active_technical_value() or 0.0
        phys_s = self._ww_format_physical_qty(physical_qty)
        factor_s = self._ww_format_physical_qty(factor) if factor else ''
        if flow in ('Plate', 'Sheet'):
            return _('Sheets: %(qty)s | m² per sheet: %(factor)s') % {
                'qty': phys_s, 'factor': factor_s,
            }
        if flow == 'Wood':
            return _('Pieces: %(qty)s | lm per piece: %(factor)s') % {
                'qty': phys_s, 'factor': factor_s,
            }
        if flow == 'Piece':
            return _('Pieces: %(qty)s') % {'qty': phys_s}
        if flow == 'Roll':
            return _('Rolls: %(qty)s | m² per roll: %(factor)s') % {
                'qty': phys_s, 'factor': factor_s,
            }
        return ''

    def _ww_report_physical_label(self, physical_qty):
        """e.g. '6 platen' for delivery columns."""
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow:
            return ''
        phys_s = self._ww_format_physical_qty(physical_qty)
        unit = {
            'Plate': _('sheets'),
            'Sheet': _('sheets'),
            'Wood': _('pieces'),
            'Piece': _('pieces'),
            'Roll': _('rolls'),
        }.get(flow, '')
        return '%s %s' % (phys_s, unit)

    def _ww_report_volume_label(self, technical_qty):
        """e.g. 'Volume: 18.75 m²'."""
        self.ensure_one()
        flow = self.product_tmpl_id.x_product_flow
        if not flow or flow == 'Piece':
            return ''
        unit = self._get_technical_unit_label() or ''
        qty_s = self._ww_format_physical_qty(technical_qty)
        return _('Volume: %(qty)s %(unit)s') % {'qty': qty_s, 'unit': unit}

