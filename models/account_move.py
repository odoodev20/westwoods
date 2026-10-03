# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _ww_report_subtitle(self):
        """Invoice line subtitle matching SO style."""
        self.ensure_one()
        product = self.product_id
        if not product or not product.product_tmpl_id.x_product_flow:
            return ''
        factor = product._get_active_technical_value() or 0.0
        qty = self.quantity or 0.0
        physical = (qty / factor) if factor > 0 else qty
        # Prefer linked sale line physical if available
        if self.sale_line_ids:
            sol = self.sale_line_ids[:1]
            if sol.x_product_flow:
                physical = sol._get_physical_quantity()
        return product._ww_report_subtitle(physical)
