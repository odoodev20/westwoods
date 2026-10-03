# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    x_ww_is_b2b = fields.Boolean(
        string='West-Woods B2B Website',
        default=False,
        help='Enable professional B2B behaviour on this website: '
             'volume-tier columns on the variant matrix, and stricter '
             'handling of customer-specific prices (no public cache).',
    )
