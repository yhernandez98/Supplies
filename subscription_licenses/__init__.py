# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizard
import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    """Limpiar datos de name (Char) antes de convertir a Many2one."""
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        _logger.info("=== PRE_INIT_HOOK: Limpiando datos del campo name ===")
        
        # Verificar si la tabla license_template existe
        cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'license_template'
            )
        """)
        table_exists = cr.fetchone()[0]
        
        if not table_exists:
            _logger.info("La tabla license_template no existe, no hay datos que limpiar.")
            return
        
        # Verificar si el campo name existe y es de tipo char
        cr.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            AND table_name = 'license_template' 
            AND column_name = 'name'
        """)
        column_info = cr.fetchone()
        
        if not column_info:
            _logger.info("El campo name no existe, no hay datos que limpiar.")
            return
        
        column_type = column_info[1]
        
        # Si ya es integer (Many2one), no hay nada que hacer
        if column_type == 'integer':
            _logger.info("El campo name ya es Many2one (integer), limpieza no necesaria.")
            return
        
        # Si no es texto, no podemos limpiar
        if column_type not in ('character varying', 'text', 'varchar'):
            _logger.warning("El campo name tiene un tipo inesperado: %s", column_type)
            return
        
        _logger.info("El campo name es de tipo texto (%s), eliminando columna...", column_type)
        
        # ELIMINAR la columna completamente para que Odoo la cree como Many2one desde cero
        cr.execute("""
            ALTER TABLE license_template 
            DROP COLUMN IF EXISTS name
        """)
        
        _logger.info("✓ Columna name eliminada")
        _logger.info("Odoo creará la columna name como Many2one (integer) desde cero")
        _logger.info("Después de actualizar, podrás asignar categorías manualmente")
        
        cr.commit()
        _logger.info("=== PRE_INIT_HOOK COMPLETADO ===")
        
    except Exception as e:
        _logger.error('ERROR EN pre_init_hook: %s', str(e), exc_info=True)
        try:
            cr.rollback()
        except:
            pass
        # Re-lanzar el error para que se vea claramente
        raise


def post_init_hook(env):
    """Eliminar vista problemática y rellenar fecha de asignación vacía en equipos."""
    # 1) Rellenar Fecha de Asignación en registros que la tengan vacía
    try:
        from datetime import date
        env.cr.execute("""
            SELECT e.id, e.assignment_id, a.start_date
            FROM license_equipment e
            JOIN license_assignment a ON a.id = e.assignment_id
            WHERE e.assignment_date IS NULL
        """)
        rows = env.cr.fetchall()
        today = date.today().isoformat()
        for (equip_id, assignment_id, start_date) in rows:
            fill_date = (start_date.isoformat() if start_date else today)
            env.cr.execute(
                "UPDATE license_equipment SET assignment_date = %s WHERE id = %s",
                (fill_date, equip_id)
            )
        if rows:
            env.cr.commit()
            _logger.info('✅ Fecha de asignación rellenada en %d equipo(s)', len(rows))
    except Exception as e:
        env.cr.rollback()
        _logger.warning('⚠️ Relleno de assignment_date: %s', str(e))

    # 2) Eliminar vista problemática con xpath obsoleto
    try:
        env.cr.execute("""
            DELETE FROM ir_ui_view 
            WHERE name = 'subscription.subscription.form.license.integration' 
            AND model = 'subscription.subscription'
            AND id IN (
                SELECT res_id FROM ir_model_data 
                WHERE module = 'subscription_licenses' 
                AND name = 'view_subscription_subscription_form_license_integration'
            )
        """)
        env.cr.execute("""
            DELETE FROM ir_model_data 
            WHERE module = 'subscription_licenses' 
            AND name = 'view_subscription_subscription_form_license_integration'
        """)
        env.cr.commit()
        _logger.info('✅ Vista antigua eliminada exitosamente en post_init_hook')
    except Exception as e:
        env.cr.rollback()
        _logger.warning('⚠️ No se pudo eliminar la vista antigua (puede que no exista): %s', str(e))

    # 3) Rellenar provider_partner_id en license.provider.stock para que la pestaña Licencias muestre las líneas
    try:
        env.cr.execute("""
            UPDATE license_provider_stock s
            SET provider_partner_id = p.id
            FROM license_provider_partner p
            WHERE s.provider_id = p.partner_id
              AND (s.provider_partner_id IS NULL OR s.provider_partner_id != p.id)
        """)
        n = env.cr.rowcount
        if n:
            env.cr.commit()
            _logger.info('✅ provider_partner_id rellenado en %d línea(s) de stock', n)
    except Exception as e:
        env.cr.rollback()
        _logger.warning('⚠️ Relleno provider_partner_id: %s', str(e))

