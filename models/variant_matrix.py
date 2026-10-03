# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_ww_variant_matrix_display = fields.Selection(
        selection=[
            ('auto', 'Auto'),
            ('show', 'Show'),
            ('hide', 'Hide'),
        ],
        string='Variant Matrix Display',
        default='auto',
        help='Auto: show matrix only when more than one sellable variant exists.\n'
             'Show: always show. Hide: never show.',
    )

    def _ww_matrix_variants(self):
        self.ensure_one()
        variants = self.product_variant_ids.filtered(lambda p: p.active)
        result = self.env['product.product']
        for variant in variants:
            if hasattr(variant, '_is_variant_possible') and not variant._is_variant_possible():
                continue
            result |= variant
        return result.sorted(lambda p: p.id)

    def _ww_should_show_matrix(self):
        self.ensure_one()
        mode = self.x_ww_variant_matrix_display or 'auto'
        if mode == 'hide':
            return False
        variants = self._ww_matrix_variants()
        if mode == 'show':
            return bool(variants)
        return len(variants) > 1

    def _ww_matrix_varying_attributes(self):
        self.ensure_one()
        variants = self._ww_matrix_variants()
        varying = []
        for line in self.attribute_line_ids:
            values = variants.mapped(
                lambda v: v.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_line_id == line
                )[:1]
            )
            unique = {v.id for v in values if v}
            if len(unique) > 1:
                varying.append(line)
        return varying

    def _ww_get_volume_tiers(self, pricelist, product=None):
        """Collect West-Woods volume rules from the active pricelist for this template/variant.

        Returns a list of dicts sorted by threshold ascending:
        {basis, threshold, technical_min, label}
        """
        self.ensure_one()
        if not pricelist:
            return []
        domain = [
            ('pricelist_id', '=', pricelist.id),
            ('x_ww_volume_threshold_basis', 'in', ('physical', 'packs')),
            ('x_ww_threshold_quantity', '>', 0),
        ]
        # Scope: global, category, template or variant
        items = self.env['product.pricelist.item'].sudo().search(domain)
        applicable = self.env['product.pricelist.item']
        for item in items:
            if item.applied_on == '3_global':
                applicable |= item
            elif item.applied_on == '2_product_category' and item.categ_id and self.categ_id:
                if self.categ_id == item.categ_id or (
                    hasattr(self.categ_id, 'parents_and_self') and item.categ_id in self.categ_id.parents_and_self
                ):
                    applicable |= item
            elif item.applied_on == '1_product' and item.product_tmpl_id == self:
                applicable |= item
            elif item.applied_on == '0_product_variant' and product and item.product_id == product:
                applicable |= item
            elif item.product_tmpl_id == self or (product and item.product_id == product):
                applicable |= item

        tiers = []
        seen = set()
        for item in applicable.sorted(lambda i: i.min_quantity):
            key = (item.x_ww_volume_threshold_basis, item.x_ww_threshold_quantity, item.min_quantity)
            if key in seen:
                continue
            seen.add(key)
            basis = item.x_ww_volume_threshold_basis
            thr = item.x_ww_threshold_quantity
            if basis == 'packs':
                label = 'From %s pack(s)' % (int(thr) if thr == int(thr) else thr)
            else:
                label = 'From %s units' % (int(thr) if thr == int(thr) else thr)
            tiers.append({
                'id': item.id,
                'basis': basis,
                'threshold': thr,
                'technical_min': item.min_quantity,
                'label': label,
                'item': item,
            })
        return tiers

    def _ww_show_b2b_tiers(self, website=None):
        """Whether to show professional volume-tier columns."""
        website = website or self.env['website'].get_current_website()
        if website and website.x_ww_is_b2b:
            return True
        # Authenticated portal/internal user on any site may see tiers of their pricelist
        user = self.env.user
        if user and not user._is_public():
            return True
        return False

    def _ww_get_variant_matrix_rows(self, pricelist=None, currency=None, website=None):
        """Build server-side matrix rows (SEO-friendly).

        On B2B / logged-in context, adds volume-tier price columns when rules exist.
        """
        self.ensure_one()
        if not self._ww_should_show_matrix():
            return []

        website = website or self.env['website'].get_current_website()
        variants = self._ww_matrix_variants()
        attr_lines = self._ww_matrix_varying_attributes()
        flow = self.x_product_flow
        rows = []
        any_pack = False
        show_tiers = self._ww_show_b2b_tiers(website=website)
        # Template-level tiers as column headers (variant-specific prices filled per row)
        tiers = self._ww_get_volume_tiers(pricelist) if show_tiers and pricelist else []

        for variant in variants:
            attr_cells = []
            for line in attr_lines:
                ptav = variant.product_template_attribute_value_ids.filtered(
                    lambda v: v.attribute_line_id == line
                )[:1]
                attr_cells.append({
                    'attribute_id': line.attribute_id.id,
                    'attribute_name': line.attribute_id.name,
                    'value_id': ptav.id if ptav else False,
                    'value_name': ptav.name if ptav else '—',
                    'ptav_id': ptav.id if ptav else False,
                })

            factor = variant._get_active_technical_value() or 0.0
            pack_mode = variant._get_effective_pack_sale_mode()
            units_pack = variant._get_units_per_pack() or 0
            if pack_mode != 'none' and units_pack > 0:
                any_pack = True

            try:
                if pricelist:
                    unit_price = pricelist._get_product_price(
                        variant, 1.0, currency=currency,
                    )
                else:
                    unit_price = variant._get_ww_effective_base_price()
            except Exception:
                unit_price = variant._get_ww_effective_base_price()

            derived = unit_price * factor if factor > 0 else 0.0
            orderable = variant._ww_is_orderable() if flow else True

            # Per-tier prices for this variant
            tier_cells = []
            for tier in tiers:
                qty = tier['technical_min'] or 1.0
                try:
                    tier_unit = pricelist._get_product_price(
                        variant, qty, currency=currency,
                    ) if pricelist else unit_price
                except Exception:
                    tier_unit = unit_price
                advantage = 0.0
                if unit_price and tier_unit is not None and unit_price > 0:
                    advantage = max(0.0, (unit_price - tier_unit) / unit_price * 100.0)
                tier_cells.append({
                    'unit_price': tier_unit,
                    'derived_price': (tier_unit or 0.0) * factor if factor > 0 else 0.0,
                    'advantage_pct': advantage,
                    'label': tier['label'],
                })

            rows.append({
                'product_id': variant.id,
                'display_name': variant.display_name,
                'attr_cells': attr_cells,
                'factor': factor,
                'factor_label': variant._get_factor_label(),
                'tech_unit': variant._get_technical_unit_label(),
                'physical_label': variant._get_physical_unit_label(),
                'pack_mode': pack_mode,
                'units_per_pack': units_pack,
                'unit_price': unit_price,
                'derived_price': derived,
                'orderable': orderable,
                'ptav_ids': variant.product_template_attribute_value_ids.ids,
                'tier_cells': tier_cells,
            })

        return {
            'rows': rows,
            'attr_lines': [{
                'id': line.id,
                'name': line.attribute_id.name,
            } for line in attr_lines],
            'flow': flow,
            'show_pack_column': any_pack,
            'show_tiers': bool(tiers),
            'tiers': [{'label': t['label'], 'id': t['id']} for t in tiers],
            'factor_header': {
                'Plate': 'm² / sheet',
                'Wood': 'lm / piece',
                'Piece': '',
                'Roll': 'm² / roll',
            }.get(flow, ''),
            'unit_price_header': {
                'Plate': '€ / m²',
                'Wood': '€ / lm',
                'Piece': '€ / piece',
                'Roll': '€ / m²',
            }.get(flow, 'Price'),
            'derived_price_header': {
                'Plate': '€ / sheet',
                'Wood': '€ / piece',
                'Piece': '€ / piece',
                'Roll': '€ / roll',
            }.get(flow, 'Price / unit'),
            'is_b2b': bool(website and website.x_ww_is_b2b),
        }
