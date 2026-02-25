from . import controllers
from . import models
from . import wizard
import logging
from datetime import datetime, date, time, timedelta

_logger = logging.getLogger(__name__)

# Horas fijas para los crons del flujo (noche/madrugada; servidor)
CRON_NEXTCALL_HOURS = {
    'subscription_nocount.ir_cron_subscription_sync_last_day': 22,
    'subscription_nocount.ir_cron_subscription_save_billable': 23,
    'subscription_nocount.ir_cron_subscription_sync_first_day': 3,
    'subscription_nocount.ir_cron_subscription_apply_trm': 2,
    'subscription_nocount.ir_cron_subscription_proformas_from_saved': 6,
}


def post_init_hook(env):
    """Después de instalar: reparar menús huérfanos, ocultar menús de sale_subscription y borrar datos de histórico mensual (si existen)."""
    # Reparar menús cuyo parent_id apunta a un registro que ya no existe (ej. error "No podemos encontrar los registros con el ID 1260")
    try:
        Menu = env['ir.ui.menu']
        env.cr.execute("SELECT id FROM ir_ui_menu")
        existing_ids = {row[0] for row in env.cr.fetchall()}
        env.cr.execute("""
            SELECT id, name, parent_id FROM ir_ui_menu
            WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM ir_ui_menu)
        """)
        orphaned = env.cr.fetchall()
        if orphaned:
            fallback = env.ref('sale.menu_sale_root', raise_if_not_found=False)
            if fallback:
                for mid, name, pid in orphaned:
                    Menu.browse(mid).write({'parent_id': fallback.id})
                    _logger.info('Menú huérfano reparado: "%s" (ID %s), parent %s -> Ventas (ID %s)', name, mid, pid, fallback.id)
                env.cr.commit()
    except Exception as e:
        _logger.warning('No se pudieron reparar menús huérfanos en post_init_hook: %s', e)

    # Borrar registros de histórico mensual (modelos ya eliminados del módulo)
    for table in ('subscription_monthly_report_grouped_rel', 'subscription_monthly_report', 'subscription_monthly_grouped', 'subscription_monthly_snapshot'):
        try:
            env.cr.execute('DELETE FROM ' + table)
        except Exception:
            pass
    try:
        hidden_count = 0
        
        # Buscar el menú principal
        main_menu = env.ref('sale_subscription.menu_sale_subscription', raise_if_not_found=False)
        if not main_menu:
            _logger.warning('⚠️ No se encontró el menú principal "sale_subscription.menu_sale_subscription" en post_init_hook')
            return
        
        # Ocultar el menú principal
        if main_menu.active:
            main_menu.write({'active': False})
            hidden_count += 1
            _logger.info('✅ Menú principal "%s" (ID: %s) ocultado en post_init_hook', main_menu.name, main_menu.id)
        else:
            _logger.info('ℹ️ Menú principal "%s" (ID: %s) ya estaba oculto en post_init_hook', main_menu.name, main_menu.id)
        
        # Función recursiva para ocultar todos los hijos
        def hide_children(parent_id):
            nonlocal hidden_count
            child_menus = env['ir.ui.menu'].search([
                ('parent_id', '=', parent_id)
            ])
            for child in child_menus:
                if child.active:
                    child.write({'active': False})
                    hidden_count += 1
                    _logger.info('✅ Menú hijo "%s" (ID: %s) ocultado en post_init_hook', child.name, child.id)
                # Ocultar también los hijos de este menú (recursivo)
                hide_children(child.id)
        
        # Ocultar todos los hijos del menú principal (recursivamente)
        hide_children(main_menu.id)
        
        if hidden_count > 0:
            env.cr.commit()
            _logger.info('✅ Total de menús ocultados en post_init_hook: %s', hidden_count)
    except Exception as e:
        _logger.error('❌ Error al ocultar menús de sale_subscription en post_init_hook: %s', str(e), exc_info=True)

    # Asignar próximas ejecuciones a los crons del flujo (horas fijas)
    try:
        now = datetime.now()
        for xml_id, hour in CRON_NEXTCALL_HOURS.items():
            try:
                cron = env.ref(xml_id, raise_if_not_found=False)
                if not cron:
                    continue
                # Próxima ejecución: hoy o mañana a la hora indicada
                next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run = next_run + timedelta(days=1)
                cron.write({'nextcall': next_run})
                _logger.info('Cron %s: próxima ejecución %s', cron.name, next_run)
            except Exception as e:
                _logger.warning('No se pudo asignar hora al cron %s: %s', xml_id, e)
    except Exception as e:
        _logger.warning('Error asignando horas a crons en post_init_hook: %s', e)
