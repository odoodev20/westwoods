# -*- coding: utf-8 -*-
{
    'name': 'WestWoods Customizations',
    'version': '19.0.1.1.0',
    'category': 'Sales/Sales',
    'summary': 'Physical to Technical unit conversion for sheets, rolls, packs and pieces',
    'description': """
WestWoods Customizations
========================
Physical → Technical unit conversion for industrial e-commerce / ERP.

* Product template & variant conversion factors
* Backend SO physical qty fields with auto technical qty
* Website: physical qty for shopper; technical qty on backend
* Product page: unit price, factor, live calculation
* Cart & checkout line breakdown
* Stock quant physical count
* Delivery / picking PDF physical labels
    """,
    'author': 'WestWoods',
    'website': 'https://www.westwoods.be',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'website_sale',
    ],
    'data': [
        'views/product_views.xml',
        'views/sale_views.xml',
        'views/stock_views.xml',
        'views/report_stockpicking.xml',
        'views/report_delivery_slip.xml',
        'views/website_sale_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'westwoods/static/src/js/westwoods_pricing.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
