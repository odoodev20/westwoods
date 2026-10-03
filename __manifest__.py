# -*- coding: utf-8 -*-
{
    'name': 'WestWoods Customizations',
    'version': '19.0.11.0.0',
    'category': 'Sales/Sales',
    'summary': 'Physical to Technical unit conversion — Plate, Wood, Piece, Roll + Pack Sale',
    'description': """
WestWoods Customizations (Phase 1 data model)
=============================================
Product Flows: Plate, Wood, Piece, Roll (spec v1.0).
Pack Sale is a generic layer (None / Optional / Required + Units per Pack).
Physical → technical conversion on sales and website cart.
    """,
    'author': 'Hasibul Islam',
    'website': 'https://hasib.odoo.com/',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'website_sale',
        'account',
    ],
    'data': [
        'views/product_views.xml',
        'views/sale_views.xml',
        'views/stock_views.xml',
        'views/report_stockpicking.xml',
        'views/report_saleorder.xml',
        'views/report_invoice.xml',
        'views/report_delivery_slip.xml',
        'views/website_sale_templates.xml',
        'views/pricelist_views.xml',
        'views/category_views.xml',
        'views/website_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'westwoods/static/src/js/westwoods_pricing.js',
            'westwoods/static/src/js/westwoods_matrix.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
