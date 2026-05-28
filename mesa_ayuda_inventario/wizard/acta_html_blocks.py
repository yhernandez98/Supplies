# -*- coding: utf-8 -*-
"""Fragmentos HTML del acta de visita (f-strings: evita ValueError con % en CSS gradientes)."""

from markupsafe import Markup, escape

from odoo import _

_D = 'd' + 'iv'

_MESA_ACTA_BLOCK_WRAP = (
    'margin-bottom:16px;border:1px solid #c8e6d4;border-radius:8px;overflow:hidden;'
    'background:#ffffff;box-shadow:0 1px 4px rgba(61,165,114,0.12);'
)
_MESA_ACTA_TH_ROW = 'background:linear-gradient(180deg,#ecf8f1 0%,#d8f0e3 100%);'
_MESA_ACTA_TH_CELL = (
    'padding:10px 8px;text-align:center;border:1px solid #c8e6d4;'
    'color:#2d7d57;font-weight:700;'
)
_MESA_ACTA_TD_CELL = (
    'padding:10px 8px;vertical-align:top;border:1px solid #d4edda;color:#000000;'
)
_MESA_ACTA_REALIZADO_BAR = (
    'background:linear-gradient(180deg,#ecf8f1 0%,#d8f0e3 100%);padding:10px 8px;'
    'font-weight:700;color:#2d7d57;text-align:center;border-bottom:1px solid #c8e6d4;'
)
_MESA_ACTA_FLAG_BTN = (
    'display:inline-block;margin:0 6px 6px 0;padding:6px 12px;border-radius:999px;'
    'border:1px solid #b8e5cc;background:#ffffff;color:#2d7d57;font-size:0.82rem;'
    'font-weight:600;cursor:pointer;user-select:none;'
)
_MESA_ACTA_FLAG_BTN_ACTIVE = (
    'display:inline-block;margin:0 6px 6px 0;padding:6px 12px;border-radius:999px;'
    'border:1px solid #3da572;background:#d8f0e3;color:#1a4d32;font-size:0.82rem;'
    'font-weight:700;cursor:pointer;user-select:none;'
)

MESA_ACTA_FOLLOWUP_FLAG_KEYS = (
    'equipment_change',
    'component_change',
    'maintenance_repair',
)


def mesa_acta_realizado_flags_html(
    lbl_equipment_change='Cambio de Equipo',
    lbl_component_change='Cambio de Componente',
    lbl_maintenance_repair='Mantenimiento/Reparación',
    active_flag_keys=None,
):
    """Botones conmutables en «Realizado» (se leen al completar la visita)."""
    o, c = f'<{_D}', f'</{_D}>'
    active = set(active_flag_keys or ())
    flags = (
        ('equipment_change', lbl_equipment_change),
        ('component_change', lbl_component_change),
        ('maintenance_repair', lbl_maintenance_repair),
    )
    buttons = []
    for key, label in flags:
        is_on = '1' if key in active else '0'
        style = _MESA_ACTA_FLAG_BTN_ACTIVE if is_on == '1' else _MESA_ACTA_FLAG_BTN
        buttons.append(
            f'<span class="mesa-acta-flag-btn" contenteditable="false" role="button" tabindex="0"'
            f' data-mesa-acta-flag="{key}" data-mesa-acta-flag-active="{is_on}"'
            f' style="{style}">{label}</span>'
        )
    return (
        f'{o} class="mesa-acta-realizado-flags" data-mesa-acta-flags="1" contenteditable="false"'
        f' style="padding:10px 12px 4px;border-bottom:1px solid #e8f5ee;background:#f6fcf8;">'
        f'{"".join(buttons)}{c}'
    )


def mesa_acta_equipment_block_html(
    lot_id, th_serie, th_placa, th_prod, serial, plate, prod, th_realizado,
    realizado_inner='<p><br></p>',
    lbl_equipment_change='Cambio de Equipo',
    lbl_component_change='Cambio de Componente',
    lbl_maintenance_repair='Mantenimiento/Reparación',
    include_followup_flags=True,
    active_flag_keys=None,
):
    """Bloque HTML: un equipo en el acta (tabla Serie/Placa/Producto + zona Realizado)."""
    o, c = f'<{_D}', f'</{_D}>'
    flags_html = ''
    if include_followup_flags:
        flags_html = mesa_acta_realizado_flags_html(
            lbl_equipment_change, lbl_component_change, lbl_maintenance_repair,
            active_flag_keys=active_flag_keys,
        )
    return (
        f'{o} style="{_MESA_ACTA_BLOCK_WRAP}">'
        f'<table data-mesa-acta-equipment="1" data-mesa-acta-equipment-lot-id="{lot_id}" '
        f'style="width:100%;border-collapse:collapse;margin:0;">'
        f'<thead><tr style="{_MESA_ACTA_TH_ROW}">'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_serie}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_placa}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_prod}</th>'
        f'</tr></thead><tbody><tr style="background:#ffffff;">'
        f'<td style="{_MESA_ACTA_TD_CELL}">{serial}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{plate}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{prod}</td>'
        f'</tr></tbody></table>'
        f'{o} style="border-top:1px solid #c8e6d4;">'
        f'{o} style="{_MESA_ACTA_REALIZADO_BAR}">{th_realizado}{c}'
        f'{flags_html}'
        f'{o} class="mesa-acta-realizado-notes" style="background:#ffffff;padding:12px 14px;min-height:3.5rem;">'
        f'{realizado_inner}{c}{c}{c}'
    )


def mesa_acta_participant_partner_block_html(
    partner_id, th_name, th_email, th_phone, name, email, phone, th_realizado,
    realizado_inner='<p><br></p>',
):
    """Bloque HTML: contacto del cliente en el acta."""
    o, c = f'<{_D}', f'</{_D}>'
    return (
        f'{o} data-mesa-acta-participant-partner-id="{partner_id}" style="{_MESA_ACTA_BLOCK_WRAP}">'
        f'<table style="width:100%;border-collapse:collapse;margin:0;">'
        f'<thead><tr style="{_MESA_ACTA_TH_ROW}">'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_name}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_email}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_phone}</th>'
        f'</tr></thead><tbody><tr style="background:#ffffff;">'
        f'<td style="{_MESA_ACTA_TD_CELL}">{name}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{email}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{phone}</td>'
        f'</tr></tbody></table>'
        f'{o} style="border-top:1px solid #c8e6d4;">'
        f'{o} style="{_MESA_ACTA_REALIZADO_BAR}">{th_realizado}{c}'
        f'{o} style="background:#ffffff;padding:12px 14px;min-height:3.5rem;">'
        f'{realizado_inner}{c}{c}{c}'
    )


def mesa_acta_participant_user_block_html(
    user_id, th_name, th_login, th_email, name, login, email, th_realizado,
    realizado_inner='<p><br></p>',
):
    """Bloque HTML: usuario del cliente en el acta (legacy)."""
    o, c = f'<{_D}', f'</{_D}>'
    return (
        f'{o} data-mesa-acta-participant-user-id="{user_id}" style="{_MESA_ACTA_BLOCK_WRAP}">'
        f'<table style="width:100%;border-collapse:collapse;margin:0;">'
        f'<thead><tr style="{_MESA_ACTA_TH_ROW}">'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_name}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_login}</th>'
        f'<th style="{_MESA_ACTA_TH_CELL}">{th_email}</th>'
        f'</tr></thead><tbody><tr style="background:#ffffff;">'
        f'<td style="{_MESA_ACTA_TD_CELL}">{name}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{login}</td>'
        f'<td style="{_MESA_ACTA_TD_CELL}">{email}</td>'
        f'</tr></tbody></table>'
        f'{o} style="border-top:1px solid #c8e6d4;">'
        f'{o} style="{_MESA_ACTA_REALIZADO_BAR}">{th_realizado}{c}'
        f'{o} style="background:#ffffff;padding:12px 14px;min-height:3.5rem;">'
        f'{realizado_inner}{c}{c}{c}'
    )


# ----- Ficha equipo / tablas en descripción de tickets (panel, retiro, solicitud acta) -----
# Paleta alineada a helpdesk_ticket_executive (--mesa-pastel-blue-*)
_MESA_TICKET_HEADER_BG = '#2d7d57'
_MESA_TICKET_HEADER_BORDER = '#266b47'
_MESA_TICKET_ACCENT_BAR = '#3da572'
_MESA_TICKET_KV_LABEL_BG = '#d8f0e3'
_MESA_TICKET_KV_LABEL_BORDER = '#b8e5cc'

# f-strings: el CSS usa width:34%% y similares; con operador %% falla (ValueError: ';').
_MESA_TICKET_DETAIL_BAR = (
    f'height:6px;background-color:{_MESA_TICKET_ACCENT_BAR};margin:0 0 10px;border-radius:2px;'
)
_MESA_TICKET_KV_TH = (
    f'padding:8px 10px;text-align:left;vertical-align:top;width:34%;'
    f'background-color:{_MESA_TICKET_KV_LABEL_BG};color:#0d2544;font-weight:700;'
    f'border:1px solid {_MESA_TICKET_KV_LABEL_BORDER};'
)
_MESA_TICKET_KV_TD = (
    'padding:8px 10px;text-align:left;vertical-align:top;'
    'background-color:#ffffff;color:#000000;font-weight:400;border:1px solid #cbd5e1;'
)
_MESA_TICKET_TBL_TH = (
    f'padding:8px 10px;text-align:left;vertical-align:top;'
    f'background-color:{_MESA_TICKET_HEADER_BG};color:#ffffff;font-weight:700;'
    f'border:1px solid {_MESA_TICKET_HEADER_BORDER};'
)
_MESA_TICKET_TBL_TD = (
    'padding:8px 10px;text-align:left;vertical-align:top;'
    'background-color:#ffffff;color:#000000;border:1px solid #cbd5e1;'
)
_MESA_TICKET_SECTION_TITLE = (
    'margin:20px 0 8px;font-weight:700;color:#000000;font-size:0.95rem;'
)
_MESA_TICKET_SUMMARY_P = 'margin:0 0 6px;line-height:1.45;color:#1f2937;font-size:13px;'
_MESA_TICKET_TBL_WRAP = (
    'width:100%;border-collapse:collapse;margin:0 0 16px;table-layout:fixed;'
)
# Anchos por columna (licencias equipo: 6 columnas)
_MESA_TICKET_LICENSE_COL_WIDTHS = ('26%', '11%', '22%', '11%', '11%', '9%')


def mesa_retiro_ticket_summary_html(search_mode_label, partner_name, result_label=None):
    """Resumen del retiro en líneas separadas (compatible widget html helpdesk)."""
    parts = [
        Markup('<p style="%s">%s</p>') % (
            _MESA_TICKET_SUMMARY_P,
            escape(_('Registro desde Retiro de Usuario/Equipo (Servicio al cliente/ Mesa de Ayuda).')),
        ),
        Markup('<p style="%s"><strong>%s</strong> %s</p>') % (
            _MESA_TICKET_SUMMARY_P,
            escape(_('Busqueda:')),
            escape(search_mode_label or ''),
        ),
        Markup('<p style="%s"><strong>%s</strong> %s</p>') % (
            _MESA_TICKET_SUMMARY_P,
            escape(_('Cliente:')),
            escape(partner_name or ''),
        ),
    ]
    if result_label:
        parts.append(
            Markup('<p style="margin:0 0 14px;line-height:1.45;font-size:13px;">'
                    '<strong>%s</strong> %s</p>')
            % (escape(_('Resultado:')), escape(result_label))
        )
    return Markup('').join(parts)


def mesa_ticket_html_section_title(title):
    """Título de sección + barra decorativa (estilo ficha equipo en tickets)."""
    o, c = f'<{_D}', f'</{_D}>'
    return (
        f'{o} class="mesa-ticket-detail__section">'
        f'<p class="mesa-ticket-detail__title" style="{_MESA_TICKET_SECTION_TITLE}">'
        f'{escape(title)}</p>'
        f'<div class="mesa-ticket-detail__bar" style="{_MESA_TICKET_DETAIL_BAR}"></div>'
        f'{c}'
    )


def mesa_ticket_html_section_title_helpdesk(title):
    """Título para helpdesk: solo p/table (el widget no renderiza divs y muestra el código)."""
    return (
        '<p class="mesa-ticket-detail__title" style="%s">%s</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="width:100%%;border-collapse:collapse;margin:0 0 12px;">'
        '<tr><td style="height:8px;%s">&#160;</td></tr></table>'
    ) % (_MESA_TICKET_SECTION_TITLE, escape(title), _MESA_TICKET_DETAIL_BAR)


def mesa_ticket_html_kv_table(rows):
    """Tabla dos columnas (etiqueta azul claro / valor blanco)."""
    body = []
    for label, value in rows:
        body.append(
            f'<tr>'
            f'<th scope="row" style="{_MESA_TICKET_KV_TH}">{escape(label)}</th>'
            f'<td style="{_MESA_TICKET_KV_TD}">{value}</td>'
            f'</tr>'
        )
    return (
        f'<table class="mesa-ticket-detail__kv" style="width:100%;border-collapse:collapse;margin:0 0 12px;">'
        f'<tbody>{"".join(body)}</tbody></table>'
    )


def mesa_ticket_html_data_table(headers, data_rows, empty_hint='—', helpdesk_layout=False):
    """Tabla con cabecera verde Mesa de Ayuda."""
    if not data_rows:
        return f'<p style="color:#64748b;font-size:0.85rem;margin:0 0 12px;">{escape(empty_hint)}</p>'
    ncols = len(headers)
    col_widths = list(_MESA_TICKET_LICENSE_COL_WIDTHS[:ncols])
    while len(col_widths) < ncols:
        col_widths.append(f'{int(100 / ncols)}%')
    th_extra = 'font-size:13px;line-height:1.3;'
    if helpdesk_layout:
        th_extra += 'white-space:normal;word-wrap:break-word;'
    head = ''.join(
        f'<th scope="col" style="{_MESA_TICKET_TBL_TH}{th_extra}">{escape(h)}</th>'
        for h in headers
    )
    colgroup = ''
    if helpdesk_layout:
        colgroup = '<colgroup>' + ''.join(
            f'<col style="width:{w};"/>' for w in col_widths
        ) + '</colgroup>'
    body = []
    for row in data_rows:
        cells = []
        for idx, cell in enumerate(row):
            td_style = _MESA_TICKET_TBL_TD + 'font-size:13px;line-height:1.35;'
            if helpdesk_layout:
                if idx >= max(0, ncols - 3):
                    td_style += 'white-space:nowrap;'
                else:
                    td_style += 'word-wrap:break-word;overflow-wrap:break-word;'
            cells.append(f'<td style="{td_style}">{cell}</td>')
        body.append(f'<tr>{"".join(cells)}</tr>')
    return (
        f'<table class="mesa-ticket-detail__data" style="{_MESA_TICKET_TBL_WRAP}">'
        f'{colgroup}<thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )
