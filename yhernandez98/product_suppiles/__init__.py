# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    """Marcar todos los elementos asociados existentes como Sin Costo (has_cost=False)."""
    env.cr.execute(
        "UPDATE stock_lot_supply_line SET has_cost = false WHERE has_cost IS NULL"
    )