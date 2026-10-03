# -*- coding: utf-8 -*-
"""Post-init / post-migrate data alignment for Phase 1 Product Flows."""


def post_init_hook(env):
    """Migrate legacy Product Flow values to spec v1.0 keys.

    Sheet → Plate
    Pack  → Piece (Pack is no longer a Product Flow; Pack Sale is separate)
    """
    cr = env.cr
    # product.template
    cr.execute(
        "UPDATE product_template SET x_product_flow = 'Plate' "
        "WHERE x_product_flow = 'Sheet'"
    )
    cr.execute(
        "UPDATE product_template SET x_product_flow = 'Piece' "
        "WHERE x_product_flow = 'Pack'"
    )
    # Optional: if a product had Pack flow and units, leave pack mode for Phase 2 tuning
    # No automatic Pack Sale Mode assignment — business must set None/Optional/Required.
