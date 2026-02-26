# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    """Marcar todos los elementos asociados existentes como Sin Costo (has_cost=False)."""
    env.cr.execute(
        "UPDATE stock_lot_supply_line SET has_cost = false WHERE has_cost IS NULL"
    )
    # Crear acción y menús Líneas de negocio por código (evita XML que falla el esquema)
    IrModelData = env['ir.model.data']
    if not IrModelData.search([
        ('module', '=', 'product_suppiles'),
        ('name', '=', 'action_product_business_line'),
        ('model', '=', 'ir.actions.act_window'),
    ]):
        action = env['ir.actions.act_window'].create({
            'name': 'Lineas de negocio',
            'res_model': 'product.business.line',
            'view_mode': 'list,form',
            'help': '<p>Define las Lineas de negocio.</p>',
        })
        IrModelData.create({
            'name': 'action_product_business_line',
            'module': 'product_suppiles',
            'model': 'ir.actions.act_window',
            'res_id': action.id,
            'noupdate': True,
        })
        # Menús bajo Inventario > Configuración
        stock_config = env.ref('stock.menu_stock_config_settings', raise_if_not_found=False)
        if stock_config:
            menu_setting = env['ir.ui.menu'].create({
                'name': 'Configuracion Lineas de negocio',
                'parent_id': stock_config.id,
                'sequence': 100,
            })
            env['ir.ui.menu'].create({
                'name': 'Lineas de negocio',
                'parent_id': menu_setting.id,
                'action': 'ir.actions.act_window,%s' % action.id,
                'sequence': 100,
            })