# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
    """
    Hook que se ejecuta después de instalar o actualizar el módulo.
    Actualiza automáticamente todas las reglas "Salida - Transporte" 
    para que tengan picking_type_id = 43.
    """
    import logging
    _logger = logging.getLogger(__name__)
    
    _logger.info('Ejecutando post_init_hook de stock_picking_type_custom...')
    
    try:
        # Actualizar todas las reglas "Salida - Transporte"
        result = env['stock.rule'].update_transport_rules_picking_type()
        
        # El método retorna un diccionario con información, pero también podemos loguear
        _logger.info('Actualización de reglas "Salida - Transporte" completada')
        
        # Eliminar acciones de servidor vinculadas a stock.picking que generen el botón
        # "Actualizar tipo operación (salida - transporte)"
        # Buscar por nombre de la acción
        actions_by_name = env['ir.actions.server'].search([
            ('binding_model_id.model', '=', 'stock.picking'),
            '|', '|', '|',
            ('name', 'ilike', '%actualizar%tipo%operación%'),
            ('name', 'ilike', '%salida%transporte%'),
            ('name', 'ilike', '%transporte%'),
            ('name', 'ilike', '%update%picking%type%transport%'),
        ])
        
        # Buscar por código que llame al método action_update_picking_type_for_transporte_route
        actions_by_code = env['ir.actions.server'].search([
            ('binding_model_id.model', '=', 'stock.picking'),
            ('state', '=', 'code'),
            '|',
            ('code', 'ilike', '%action_update_picking_type_for_transporte_route%'),
            ('code', 'ilike', '%update_picking_type_for_transporte%'),
        ])
        
        # Combinar ambas búsquedas
        actions_to_delete = actions_by_name | actions_by_code
        
        if actions_to_delete:
            _logger.info('Eliminando %s acción(es) de servidor vinculada(s) a stock.picking relacionada(s) con actualizar tipo operación transporte', len(actions_to_delete))
            for action in actions_to_delete:
                _logger.info('  - Eliminando acción: %s (ID: %s)', action.name, action.id)
            actions_to_delete.unlink()
            _logger.info('Acciones de servidor eliminadas exitosamente')
        
    except Exception as e:
        _logger.error('Error al actualizar reglas "Salida - Transporte" en post_init_hook: %s', str(e), exc_info=True)
