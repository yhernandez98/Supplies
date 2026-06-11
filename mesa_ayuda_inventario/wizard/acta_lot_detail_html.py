# -*- coding: utf-8 -*-
"""HTML de ficha del equipo para tickets de solicitud acta (cambio de equipo, retiro, etc.)."""

from markupsafe import Markup, escape

from odoo import fields as odoo_fields
from odoo.tools import formatLang
from odoo.tools.misc import format_date

from .acta_html_blocks import (
    mesa_ticket_html_data_table,
    mesa_ticket_html_kv_table,
    mesa_ticket_html_section_title,
    mesa_ticket_html_section_title_helpdesk,
)

_D = 'd' + 'iv'


def _mesa_fmt_date(env, value):
    if not value:
        return ''
    try:
        return format_date(env, value)
    except Exception:
        return odoo_fields.Date.to_string(value) if value else ''


def _mesa_selection_label(record, field_name):
    if not record or field_name not in record._fields:
        return ''
    finfo = record._fields[field_name]
    raw = record[field_name]
    if not raw:
        return ''
    if hasattr(finfo, '_description_selection'):
        pairs = finfo._description_selection(record.env)
    else:
        sel = finfo.selection
        if callable(sel):
            pairs = sel(record)
        else:
            pairs = sel or []
    return dict(pairs).get(raw, raw)


def _mesa_lot_main_info_rows(env, lot):
    """Campos ficha del serial (imagen 3 + usuario imagen 6); sin ubicación ni costo."""
    product = lot.product_id
    servicio = ''
    if hasattr(lot, 'subscription_service_product_id') and lot.subscription_service_product_id:
        servicio = lot.subscription_service_product_id.display_name
    suscripcion = ''
    if hasattr(lot, 'active_subscription_id') and lot.active_subscription_id:
        suscripcion = lot.active_subscription_id.display_name
    plazo = ''
    if hasattr(lot, 'get_acta_reining_plazo_label'):
        plazo = lot.get_acta_reining_plazo_label() or ''
    usuario = ''
    if hasattr(lot, 'related_partner_id') and lot.related_partner_id:
        usuario = lot.related_partner_id.display_name
    entry_d = getattr(lot, 'entry_date_display', None) or getattr(lot, 'entry_date', None)
    exit_d = getattr(lot, 'exit_date_display', None) or getattr(lot, 'exit_date', None)
    return [
        ('Placa de Inventario', escape(lot.inventory_plate or '')),
        ('Placa de Seguridad', escape(lot.security_plate or '')),
        ('Hostname', escape(lot.hostname or '')),
        ('Producto', escape(product.display_name if product else '')),
        ('Referencia Interna', escape(product.default_code if product else '')),
        ('Modelo', escape(lot.model_name or '')),
        ('Código de Facturación', escape(lot.billing_code or '')),
        ('Fecha Activación Renting', escape(_mesa_fmt_date(env, entry_d))),
        ('Fecha Finalización Renting', escape(_mesa_fmt_date(env, exit_d))),
        ('Servicio', escape(servicio)),
        ('Suscripción', escape(suscripcion)),
        ('Plazo Renting', escape(plazo)),
        ('Usuario', escape(usuario)),
    ]


def _mesa_supply_line_rows(line):
    parent_serial = escape(line.lot_id.name or '') if line.lot_id else ''
    tipo = escape(_mesa_selection_label(line, 'item_type'))
    producto = escape(line.product_id.display_name if line.product_id else '')
    serial = escape(line.related_lot_id.name or '') if line.related_lot_id else ''
    row = [parent_serial, tipo, producto, serial]
    if line.has_cost:
        cost_val = line.cost_additional_value
        if not cost_val and line.related_lot_id and hasattr(line.related_lot_id, 'cost_additional_value'):
            cost_val = line.related_lot_id.cost_additional_value
        row.append(escape(formatLang(line.env, cost_val or 0.0, digits=2) if cost_val else ''))
    return row


def _mesa_license_equipment_rows(le):
    """Filas licencias pestaña equipo."""
    rows = []
    for rec in le:
        asign = rec.assignment_id.license_display_name if rec.assignment_id else ''
        if not asign and rec.assignment_id:
            asign = rec.assignment_id.display_name
        categoria = rec.license_id.display_name if rec.license_id else ''
        licencia = rec.service_product_id.display_name if rec.service_product_id else ''
        estado = _mesa_selection_label(rec, 'state')
        rows.append([
            escape(asign or ''),
            escape(categoria or ''),
            escape(licencia or ''),
            escape(_mesa_fmt_date(rec.env, rec.assignment_date)),
            escape(_mesa_fmt_date(rec.env, rec.unassignment_date)),
            escape(estado or ''),
        ])
    return rows


def _mesa_license_user_rows(le):
    rows = []
    for rec in le:
        asign = rec.assignment_id.license_display_name if rec.assignment_id else ''
        if not asign and rec.assignment_id:
            asign = rec.assignment_id.display_name
        contacto = rec.contact_id.display_name if rec.contact_id else ''
        categoria = rec.license_id.display_name if rec.license_id else ''
        licencia = rec.service_product_id.display_name if rec.service_product_id else ''
        estado = _mesa_selection_label(rec, 'state')
        rows.append([
            escape(asign or ''),
            escape(contacto or ''),
            escape(categoria or ''),
            escape(licencia or ''),
            escape(_mesa_fmt_date(rec.env, rec.assignment_date)),
            escape(_mesa_fmt_date(rec.env, rec.unassignment_date)),
            escape(estado or ''),
        ])
    return rows


def mesa_acta_lot_equipment_detail_html(env, lot):
    """Bloque HTML completo: ficha, elementos y licencias del serial."""
    if not lot:
        return ''
    lot = lot.sudo()
    o, c = f'<{_D}', f'</{_D}>'
    parts = [
        f'{o} class="mesa-acta-lot-detail mesa-ticket-detail" data-mesa-acta-lot-detail="{lot.id}" '
        f'style="margin-top:20px;padding-top:4px;">',
        mesa_ticket_html_section_title(env._('Información del equipo')),
        mesa_ticket_html_kv_table(_mesa_lot_main_info_rows(env, lot)),
    ]
    sin_costo = lot.lot_supply_line_sin_costo_ids if hasattr(lot, 'lot_supply_line_sin_costo_ids') else []
    con_costo = lot.lot_supply_line_con_costo_ids if hasattr(lot, 'lot_supply_line_con_costo_ids') else []
    if sin_costo:
        parts.append(mesa_ticket_html_section_title(env._('Elementos sin costo')))
        parts.append(mesa_ticket_html_data_table(
            [env._('Serial padre'), env._('Tipo'), env._('Producto'), env._('Serial')],
            [_mesa_supply_line_rows(ln)[:4] for ln in sin_costo],
        ))
    if con_costo:
        parts.append(mesa_ticket_html_section_title(env._('Elementos con costo')))
        parts.append(mesa_ticket_html_data_table(
            [
                env._('Serial padre'), env._('Tipo'), env._('Producto'), env._('Serial'),
                env._('Costo adicional'),
            ],
            [_mesa_supply_line_rows(ln) for ln in con_costo],
        ))
    eq_lines = env['license.equipment'].browse()
    if 'license.equipment' in env:
        Le = env['license.equipment']
        if hasattr(lot, 'license_equipment_ids') and lot.license_equipment_ids:
            eq_lines = lot.license_equipment_ids
        else:
            eq_lines = Le._equipment_tab_lines_for_lot(lot)
    parts.append(mesa_ticket_html_section_title(env._('Licencias del equipo')))
    parts.append(mesa_ticket_html_data_table(
        [
            env._('Asignación'), env._('Categoría'), env._('Licencia'),
            env._('Fecha asignación'), env._('Fecha desasignación'), env._('Estado'),
        ],
        _mesa_license_equipment_rows(eq_lines),
    ))
    if hasattr(lot, 'license_user_ids') and lot.license_user_ids:
        parts.append(mesa_ticket_html_section_title(env._('Licencias del usuario')))
        parts.append(mesa_ticket_html_data_table(
            [
                env._('Asignación'), env._('Contacto'), env._('Categoría'), env._('Licencia'),
                env._('Fecha asignación'), env._('Fecha desasignación'), env._('Estado'),
            ],
            _mesa_license_user_rows(lot.license_user_ids),
        ))
    parts.append(c)
    return Markup('').join(Markup(p) for p in parts)


def mesa_acta_lot_devolucion_ticket_detail_html(env, lot):
    """Ficha para ticket (solo p/table; el widget html de helpdesk no renderiza divs)."""
    if not lot:
        return ''
    lot = lot.sudo()
    eq_lines = env['license.equipment'].browse()
    if 'license.equipment' in env:
        Le = env['license.equipment']
        if hasattr(lot, 'license_equipment_ids') and lot.license_equipment_ids:
            eq_lines = lot.license_equipment_ids.filtered(
                lambda rec: rec.state == 'assigned' and not rec.contact_id
            )
        else:
            eq_lines = Le.search([
                ('lot_id', '=', lot.id),
                ('state', '=', 'assigned'),
                ('contact_id', '=', False),
            ])
    parts = []
    kv_html = mesa_ticket_html_kv_table(
        _mesa_lot_main_info_rows(env, lot),
        skip_empty_values=True,
    )
    if kv_html:
        parts.append(Markup(
            mesa_ticket_html_section_title_helpdesk(env._('Información del equipo'))
        ))
        parts.append(Markup(kv_html))
    license_rows = _mesa_license_equipment_rows(eq_lines)
    if license_rows:
        parts.append(Markup(
            mesa_ticket_html_section_title_helpdesk(env._('Licencias del equipo'))
        ))
        parts.append(Markup(mesa_ticket_html_data_table(
            [
                env._('Asignación'), env._('Categoría'), env._('Licencia'),
                env._('Fecha asignación'), env._('Fecha desasignación'), env._('Estado'),
            ],
            license_rows,
        )))
    if not parts:
        return Markup('')
    return Markup('').join(parts)


def _mesa_license_equipment_snapshot_rows(env, snapshots):
    """Filas de tabla de ticket a partir de datos capturados antes de eliminar license.equipment."""
    rows = []
    for snap in snapshots or []:
        rows.append([
            escape(snap.get('assignment_label') or ''),
            escape(snap.get('category_name') or ''),
            escape(snap.get('license_product_name') or ''),
            escape(_mesa_fmt_date(env, snap.get('assignment_date'))),
            escape(_mesa_fmt_date(env, snap.get('unassignment_date'))),
            escape(snap.get('state_label') or ''),
        ])
    return rows


def _mesa_license_user_snapshot_rows(env, snapshots):
    rows = []
    for snap in snapshots or []:
        rows.append([
            escape(snap.get('assignment_label') or ''),
            escape(snap.get('contact_name') or ''),
            escape(snap.get('category_name') or ''),
            escape(snap.get('license_product_name') or ''),
            escape(snap.get('equipment_label') or ''),
            escape(_mesa_fmt_date(env, snap.get('assignment_date'))),
            escape(_mesa_fmt_date(env, snap.get('unassignment_date'))),
            escape(snap.get('state_label') or ''),
        ])
    return rows


def mesa_retiro_user_license_lines_ticket_html(env, license_lines=None, license_snapshots=None):
    """Tabla de licencias del usuario para ticket (mismo estilo que por placa)."""
    if license_snapshots:
        data_rows = _mesa_license_user_snapshot_rows(env, license_snapshots)
    elif license_lines:
        data_rows = _mesa_license_user_rows(license_lines)
    else:
        return Markup('<p class="text-muted">%s</p>') % escape(
            env._('No se seleccionaron licencias del usuario.')
        )
    if not data_rows:
        return Markup('<p class="text-muted">%s</p>') % escape(
            env._('No se seleccionaron licencias del usuario.')
        )
    return Markup('').join([
        Markup(mesa_ticket_html_section_title_helpdesk(
            env._('Licencias del usuario a retirar'),
        )),
        Markup(mesa_ticket_html_data_table(
            [
                env._('Asignación'),
                env._('Usuario'),
                env._('Categoría'),
                env._('Licencia'),
                env._('Equipo vinculado'),
                env._('Fecha asignación'),
                env._('Fecha desasignación'),
                env._('Estado'),
            ],
            data_rows,
            helpdesk_layout=True,
        )),
    ])


def mesa_retiro_license_lines_ticket_html(env, license_lines=None, license_snapshots=None):
    """Solo tabla de licencias seleccionadas para ticket Retirar Licencias."""
    if license_snapshots:
        data_rows = _mesa_license_equipment_snapshot_rows(env, license_snapshots)
    elif license_lines:
        data_rows = _mesa_license_equipment_rows(license_lines)
    else:
        return Markup('<p class="text-muted">%s</p>') % escape(
            env._('No se seleccionaron licencias del equipo.')
        )
    if not data_rows:
        return Markup('<p class="text-muted">%s</p>') % escape(
            env._('No se seleccionaron licencias del equipo.')
        )
    return Markup('').join([
        Markup(mesa_ticket_html_section_title_helpdesk(
            env._('Licencias del equipo a retirar'),
        )),
        Markup(mesa_ticket_html_data_table(
            [
                env._('Asignación'), env._('Categoría'), env._('Licencia'),
                env._('Fecha asignación'), env._('Fecha desasignación'), env._('Estado'),
            ],
            data_rows,
            helpdesk_layout=True,
        )),
    ])
