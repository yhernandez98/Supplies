# -*- coding: utf-8 -*-

from . import models
from . import wizard

def post_init_hook(env):
    """Limpiar vista problemática después de instalar/actualizar."""
    try:
        # Eliminar la vista problemática directamente con SQL
        env.cr.execute("""
            DELETE FROM ir_ui_view 
            WHERE name = 'stock.quant.supplies.form' 
            AND model = 'stock.quant'
        """)
        # También eliminar el registro de ir_model_data si existe
        env.cr.execute("""
            DELETE FROM ir_model_data 
            WHERE module = 'crm_sales_supplies' 
            AND name = 'view_supplies_stock_quant_form'
        """)
        env.cr.commit()
    except Exception:
        env.cr.rollback()
