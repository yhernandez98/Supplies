# -*- coding: utf-8 -*-

import re
import logging

_logger = logging.getLogger(__name__)


def _mesa_pre_init_clean_helpdesk_ticket_views(cr):
    """Limpia vistas helpdesk.ticket rotas (v.124–130). Se ejecuta solo en -u del módulo."""
    patterns = [
        (r'<attribute\s+name="invisible">mesa_ticket_detail_html</attribute>\s*', ''),
        (r'<group[^>]*string="Detalle del retiro"[^>]*>[\s\S]*?</group>\s*', ''),
        (r'<field\s+name="mesa_ticket_detail_html"[^>]*>\s*</field>\s*', ''),
        (r'<field\s+name="mesa_ticket_detail_html"[^/]*/>\s*', ''),
        (r"<attribute\s+name=\"options\">\{'style-inline':\s*'true'\}</attribute>\s*", ''),
        # Redefinición peligrosa que pudo quedar en arch_db de intentos fallidos:
        (r'description\s*=\s*fields\.Html\([^)]*\)', ''),
    ]
    compiled = [(re.compile(p, re.I), r) for p, r in patterns]

    try:
        cr.execute(
            """
            SELECT id, arch_db::text
            FROM ir_ui_view
            WHERE model = 'helpdesk.ticket'
              AND arch_db IS NOT NULL
            """
        )
    except Exception as e:
        _logger.warning('Mesa ayuda: limpieza vistas helpdesk.ticket omitida: %s', e)
        return

    for vid, arch in cr.fetchall():
        if not arch:
            continue
        text = arch
        if 'mesa_ticket_detail_html' not in text.lower() and 'style-inline' not in text:
            continue
        original = text
        for rx, repl in compiled:
            text = rx.sub(repl, text)
        if text == original:
            continue
        try:
            cr.execute('UPDATE ir_ui_view SET arch_db = %s::jsonb WHERE id = %s', (text, vid))
        except Exception:
            try:
                cr.execute('UPDATE ir_ui_view SET arch_db = %s WHERE id = %s', (text, vid))
            except Exception as e2:
                _logger.warning('Mesa ayuda: no se actualizó vista id=%s: %s', vid, e2)


def pre_init_hook(cr):
    """Limpieza de vista SQL heredada y migración de tipos de actividad obsoletos."""
    _mesa_pre_init_clean_helpdesk_ticket_views(cr)
    cr.execute('DROP VIEW IF EXISTS mesa_service_unified CASCADE')
    try:
        from odoo.tools import sql
        if sql.table_exists(cr, 'maintenance_order'):
            cr.execute(
                """
                UPDATE maintenance_order
                SET activity_type = 'visit'
                WHERE activity_type IN ('maintenance', 'inspection', 'repair', 'installation')
                """
            )
    except Exception:
        # No bloquear instalación si el entorno no expone sql.table_exists
        pass
    # Desactivar secuencias genéricas "maintenance.order" (suelen ser la causa del prefijo MO- ajeno a este módulo)
    try:
        cr.execute("UPDATE ir_sequence SET active = false WHERE code = 'maintenance.order'")
    except Exception:
        pass


def post_init_hook(env):
    """Secuencia dedicada mesa.ayuda.maintenance.order (VS-); desactiva duplicados maintenance.order."""
    import re

    cr = env.cr
    Seq = env['ir.sequence'].sudo()
    try:
        cr.execute("UPDATE ir_sequence SET active = false WHERE code = %s", ('maintenance.order',))
    except Exception:
        pass
    new_code = 'mesa.ayuda.maintenance.order'
    seq = Seq.search([('code', '=', new_code)], limit=1)
    if not seq:
        seq = Seq.create({
            'name': 'Secuencia visita técnica (Mesa ayuda)',
            'code': new_code,
            'prefix': 'VS-',
            'padding': 6,
        })
    else:
        seq.write({'prefix': 'VS-', 'active': True})
    try:
        cr.execute(
            """
            UPDATE maintenance_order
            SET name = regexp_replace(trim(name), '^(MO|VT)-', 'VS-', 'i')
            WHERE name ~* '^(MO|VT)-'
            """
        )
    except Exception:
        pass
    try:
        cr.execute('SELECT name FROM maintenance_order')
        maxn = 0
        for (name,) in cr.fetchall():
            m = re.match(r'(?i)(?:MO|VT|VS)-(\d+)$', (name or '').strip())
            if m:
                try:
                    maxn = max(maxn, int(m.group(1)))
                except ValueError:
                    continue
        if maxn and seq.number_next <= maxn:
            seq.write({'number_next': maxn + 1})
    except Exception:
        pass
    # Títulos de ticket "Visita Técnica MO-/VT-..." → "Visita Técnica VS-..." (conserva sufijo tipo (#00009))
    try:
        Ticket = env['helpdesk.ticket'].sudo()
        for ticket in Ticket.search([('maintenance_order_id', '!=', False)]):
            tname = (ticket.name or '').strip()
            if not tname:
                continue
            new_title = re.sub(r'(?i)^(Visita Técnica\s+)(MO|VT)-', r'\1VS-', tname)
            if new_title != tname:
                ticket.write({'name': new_title})
    except Exception:
        pass
    _mesa_pre_init_clean_helpdesk_ticket_views(cr)
    _mesa_touch_helpdesk_ticket_form_view(env)


def _mesa_touch_helpdesk_ticket_form_view(env):
    """Fuerza recálculo de la vista heredada de tickets tras cambios de campos XML."""
    try:
        view = env.ref(
            'mesa_ayuda_inventario.view_helpdesk_ticket_form_inherit_category',
            raise_if_not_found=False,
        )
        if view:
            view.invalidate_recordset(['arch_db'])
    except Exception:
        pass
