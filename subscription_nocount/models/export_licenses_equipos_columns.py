# -*- coding: utf-8 -*-
"""Definición de columnas exportables (Licencias / Equipos) para Excel y PDF."""

LICENSE_EXPORT_COLUMNS = [
    ('grouping', 'Agrupamiento'),
    ('product', 'Producto'),
    ('serial', 'Número de serie/lote'),
    ('inventory_plate', 'Placa de Inventario'),
    ('user', 'Usuario Asignado'),
    ('license_service', 'Licencia/Servicio Asignado'),
    ('cost', 'Costo'),
    ('currency', 'Moneda'),
]

EQUIPMENT_EXPORT_COLUMNS = [
    ('grouping', 'Agrupamiento'),
    ('product', 'Producto'),
    ('inventory_plate', 'Placa de Inventario'),
    ('serial', 'Serial/Lote'),
    ('user', 'Usuario Asignado'),
    ('cost_renting', 'Costo Renting'),
    ('cost_additional', 'Costo Adicional'),
    ('entry_date', 'Fecha Activación'),
    ('exit_date', 'Fecha Finalización'),
    ('reining_plazo', 'Plazo Renting'),
    ('tiempo_sitio', 'Tiempo En Sitio'),
    ('tiempo_restante', 'Tiempo Restante'),
    ('days_service', 'Días En Servicio'),
    ('cost_daily', 'Costo Diario'),
    ('cost_to_date', 'Costo Días En Servicio'),
]


def _license_labels():
    return dict(LICENSE_EXPORT_COLUMNS)


def _equipment_labels():
    return dict(EQUIPMENT_EXPORT_COLUMNS)


def get_license_columns_from_export_data(data):
    """Lista (key, label) según data; si no hay config, todas las columnas."""
    cfg = (data or {}).get('export_columns') if data else None
    if not cfg or cfg.get('license') is None:
        return list(LICENSE_EXPORT_COLUMNS)
    lic = cfg['license']
    return [(k, L) for k, L in LICENSE_EXPORT_COLUMNS if lic.get(k)]


def get_equipment_columns_from_export_data(data):
    cfg = (data or {}).get('export_columns') if data else None
    if not cfg or cfg.get('equipment') is None:
        return list(EQUIPMENT_EXPORT_COLUMNS)
    eq = cfg['equipment']
    return [(k, L) for k, L in EQUIPMENT_EXPORT_COLUMNS if eq.get(k)]


def license_flags_for_template(data):
    """Dict key -> bool para QWeb; sin data = todas True."""
    cfg = (data or {}).get('export_columns') if data else None
    if not cfg or cfg.get('license') is None:
        return {k: True for k, _ in LICENSE_EXPORT_COLUMNS}
    lic = cfg['license']
    return {k: bool(lic.get(k, False)) for k, _ in LICENSE_EXPORT_COLUMNS}


def equipment_flags_for_template(data):
    cfg = (data or {}).get('export_columns') if data else None
    if not cfg or cfg.get('equipment') is None:
        return {k: True for k, _ in EQUIPMENT_EXPORT_COLUMNS}
    eq = cfg['equipment']
    return {k: bool(eq.get(k, False)) for k, _ in EQUIPMENT_EXPORT_COLUMNS}


def count_active_flags(flags):
    return sum(1 for v in flags.values() if v)


def _val_live_lic(l, key):
    if key == 'grouping':
        return l.business_line_name or ''
    if key == 'product':
        return (l.product_id.display_name if l.product_id else '') or ''
    if key == 'serial':
        return (l.lot_id.name if l.lot_id else '') or ''
    if key == 'inventory_plate':
        return l.inventory_plate or ''
    if key == 'user':
        return (l.assigned_user_display_name or '').strip()
    if key == 'license_service':
        return l.license_service_name or ''
    if key == 'cost':
        return float(l.cost or 0.0)
    if key == 'currency':
        return (l.cost_currency_id.name if l.cost_currency_id else '') or ''
    return ''


def _val_monthly_lic(l, key):
    if key == 'grouping':
        return l.business_line_name or ''
    if key == 'product':
        return l.product_name or ''
    if key == 'serial':
        return l.lot_name or ''
    if key == 'inventory_plate':
        return l.inventory_plate or ''
    if key == 'user':
        au = getattr(l, 'assigned_user_name', None) or getattr(l, 'assigned_user_display_name', None) or ''
        return (au or '').strip()
    if key == 'license_service':
        return l.license_service_name or ''
    if key == 'cost':
        return float(l.cost_renting or 0.0)
    if key == 'currency':
        return (l.currency_id.name if l.currency_id else '') or ''
    return ''


def _val_live_eq(e, key):
    if key == 'grouping':
        return e.business_line_name or ''
    if key == 'product':
        return e.product_name or ''
    if key == 'inventory_plate':
        return e.inventory_plate or ''
    if key == 'serial':
        return e.lot_name or ''
    if key == 'user':
        return (e.assigned_user_display_name or '').strip()
    if key == 'cost_renting':
        return float(e.cost_renting_total or 0.0)
    if key == 'cost_additional':
        return float(e.cost_additional or 0.0)
    if key == 'entry_date':
        return str(e.entry_date) if e.entry_date else ''
    if key == 'exit_date':
        return str(e.exit_date) if e.exit_date else ''
    if key == 'reining_plazo':
        return e.reining_plazo or ''
    if key == 'tiempo_sitio':
        return e.tiempo_en_sitio_display or ''
    if key == 'tiempo_restante':
        return e.tiempo_restante_display or ''
    if key == 'days_service':
        return int(e.days_in_service or 0)
    if key == 'cost_daily':
        return float(e.cost_daily or 0.0)
    if key == 'cost_to_date':
        return float(e.cost_to_date or 0.0)
    return ''


def _val_monthly_eq(e, key):
    return _val_live_eq(e, key)


LICENSE_XLSX_NUMBER_KEYS = frozenset({'cost'})
EQUIPMENT_XLSX_MONEY_KEYS = frozenset({'cost_renting', 'cost_additional', 'cost_daily', 'cost_to_date'})
EQUIPMENT_XLSX_INT_KEYS = frozenset({'days_service'})
