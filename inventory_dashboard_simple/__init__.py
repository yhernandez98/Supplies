# -*- coding: utf-8 -*-

from . import models
from . import wizard
from . import controllers
import logging

_logger = logging.getLogger(__name__)

def pre_init_hook(cr):
    """Eliminar columna internal_ref antigua antes de inicializar el módulo."""
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        _logger.info("=== PRE_INIT_HOOK: Eliminando columna internal_ref antigua ===")
        
        # Verificar si la tabla quant_editor_wizard existe
        cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'quant_editor_wizard'
            )
        """)
        table_exists = cr.fetchone()[0]
        
        if not table_exists:
            _logger.info("La tabla quant_editor_wizard no existe, no hay nada que hacer.")
            return
        
        # Verificar si el campo internal_ref existe
        cr.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            AND table_name = 'quant_editor_wizard' 
            AND column_name = 'internal_ref'
        """)
        column_info = cr.fetchone()
        
        if not column_info:
            _logger.info("El campo internal_ref no existe, no hay nada que hacer.")
            return
        
        column_type = column_info[1]
        _logger.info("Tipo de columna internal_ref encontrado: %s", column_type)
        
        # Si es de tipo texto, eliminarlo directamente (es un wizard transitorio)
        if column_type in ('character varying', 'text', 'varchar'):
            _logger.info("Eliminando columna internal_ref de tipo texto...")
            cr.execute("""
                ALTER TABLE quant_editor_wizard 
                DROP COLUMN IF EXISTS internal_ref
            """)
            cr.commit()
            _logger.info("✓ Columna internal_ref eliminada exitosamente")
        else:
            _logger.info("El campo internal_ref ya no es de tipo texto (%s), no se requiere acción.", column_type)
        
        _logger.info("=== PRE_INIT_HOOK COMPLETADO ===")
        
    except Exception as e:
        _logger.error('ERROR EN pre_init_hook: %s', str(e), exc_info=True)
        try:
            cr.rollback()
        except:
            pass
        # Re-lanzar el error para que se vea en los logs
        raise

def post_init_hook(env):
    """Crear grupos iniciales después de instalar el módulo y recalcular campos computed."""
    try:
        env['inventory.dashboard.group'].init_groups()
        _logger.info('✅ Grupos del dashboard inicializados correctamente')
    except Exception as e:
        _logger.error('❌ Error al inicializar grupos del dashboard: %s', str(e), exc_info=True)

    # Recalcular has_excluded_supply_elements para todos los lotes
    try:
        _logger.info('=== Iniciando recálculo de has_excluded_supply_elements ===')
        StockLot = env['stock.lot']
        
        # Verificar que el campo existe
        if 'has_excluded_supply_elements' not in StockLot._fields:
            _logger.warning('⚠️ Campo has_excluded_supply_elements no encontrado en stock.lot')
        else:
            # Invalidar todo el cache primero
            env.invalidate_all()
            
            # Llamar al método de recálculo
            if hasattr(StockLot, 'recompute_has_excluded_supply_elements'):
                result = StockLot.recompute_has_excluded_supply_elements()
                _logger.info('✅ Recálculo de has_excluded_supply_elements completado: %s', result)
            else:
                _logger.warning('⚠️ Método recompute_has_excluded_supply_elements no encontrado')
                # Intentar recálculo manual
                _logger.info('Intentando recálculo manual...')
                all_lots = StockLot.search([])
                if all_lots:
                    all_lots.invalidate_cache(['has_excluded_supply_elements'])
                    all_lots._compute_has_excluded_supply_elements()
                    env.cr.commit()
                    _logger.info('✅ Recálculo manual completado para %d lotes', len(all_lots))
        
        _logger.info('=== Recálculo de has_excluded_supply_elements finalizado ===')
    except Exception as e:
        _logger.error('❌ Error al recalcular has_excluded_supply_elements: %s', str(e), exc_info=True)

    # Recalcular ubicación/contacto mostrados (jerarquía KANGU/Existencias → cliente)
    try:
        StockLot = env['stock.lot']
        if 'display_contact_id' in StockLot._fields and hasattr(StockLot, '_compute_display_location_contact'):
            todo = StockLot.search([('invdash_pending_info', '=', True)])
            if todo:
                todo._compute_display_location_contact()
                env.cr.commit()
                _logger.info(
                    '✅ display_contact_id actualizado para %s lotes pendientes de información',
                    len(todo),
                )
    except Exception as e:
        _logger.warning('Recálculo display_contact_id post-upgrade: %s', str(e), exc_info=True)

    try:
        Pick = env['stock.picking']
        if 'invdash_delivery_billing_pending' in Pick._fields and hasattr(
            Pick, '_recompute_all_delivery_billing_pending'
        ):
            n = Pick._recompute_all_delivery_billing_pending()
            _logger.info('✅ Facturación ruta entrega: %s albarán(es) pendientes recalculados', n)
    except Exception as e:
        _logger.warning('Recálculo facturación ruta entrega: %s', str(e), exc_info=True)

    # Marcar préstamos lab. ya devueltos (histórico antes del flag component_lab_loan_completed)
    try:
        Pick = env['stock.picking']
        if (
            'component_lab_loan_completed' in Pick._fields
            and 'component_lab_pending_responsible_approval' in Pick._fields
        ):
            historical = Pick.search([
                ('component_lab_return_picking_id', '!=', False),
                ('component_lab_return_picking_id.state', '=', 'done'),
                ('state', '=', 'done'),
                ('component_lab_loan_completed', '=', False),
                ('component_lab_pending_responsible_approval', '=', False),
                ('lab_responsible_user_id', '!=', False),
            ])
            if historical:
                historical.write({
                    'component_lab_loan_completed': True,
                    'component_lab_loan_active': False,
                })
                _logger.info(
                    '✅ Préstamos lab. históricos marcados como completados: %s albarán(es)',
                    len(historical),
                )
    except Exception as e:
        _logger.error('❌ Error al marcar préstamos lab. completados: %s', str(e), exc_info=True)