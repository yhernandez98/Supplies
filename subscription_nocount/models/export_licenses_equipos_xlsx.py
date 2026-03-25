# -*- coding: utf-8 -*-
from odoo import models, _


class ExportLicensesEquiposXlsx(models.AbstractModel):
    _name = 'report.subscription_nocount.report_export_licenses_equipos_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Exportar Licencias y Equipos a Excel'

    def generate_xlsx_report(self, workbook, data, subscriptions):
        if not subscriptions:
            return
        sub = subscriptions[0]

        # Datos (regeneramos las transientes igual que los botones)
        license_lines = sub._get_export_license_serial_lines()
        equipment_lines = sub._get_export_equipment_serial_lines()

        # Estilos
        h1 = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        th = workbook.add_format({'bold': True, 'bg_color': '#004f9f', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        td = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        td_center = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'center'})
        td_money = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'right', 'num_format': '#,##0.00'})

        # Hoja: Licencias
        sheet_lic = workbook.add_worksheet(_('Licencias'))
        sheet_lic.write(0, 0, _('EXPORTACION LICENCIAS'), h1)

        lic_headers = [
            'Agrupamiento',
            'Producto',
            'Número de serie/lote',
            'Placa de Inventario',
            'Usuario Asignado',
            'Licencia/Servicio Asignado',
            'Costo',
            'Moneda',
        ]
        for col, header in enumerate(lic_headers):
            sheet_lic.write(2, col, header, th)

        row = 3
        for l in license_lines:
            sheet_lic.write(row, 0, l.business_line_name or '', td)
            sheet_lic.write(row, 1, (l.product_id.display_name if l.product_id else '') or '', td)
            sheet_lic.write(row, 2, (l.lot_id.name if l.lot_id else '') or '', td)
            sheet_lic.write(row, 3, l.inventory_plate or '', td)
            _au_lic = (l.assigned_user_display_name or '').strip()
            sheet_lic.write(row, 4, _au_lic, td)
            sheet_lic.write(row, 5, l.license_service_name or '', td)
            sheet_lic.write_number(row, 6, float(l.cost or 0.0), td_money)
            sheet_lic.write(row, 7, (l.cost_currency_id.name if l.cost_currency_id else '') or '', td)
            row += 1

        # Hoja: Equipos
        sheet_eq = workbook.add_worksheet(_('Equipos'))
        sheet_eq.write(0, 0, _('EXPORTACION EQUIPOS'), h1)

        eq_headers = [
            'Agrupamiento',
            'Producto',
            'Placa de Inventario',
            'Serial/Lote',
            'Usuario Asignado',
            'Costo Renting',
            'Costo Adicional',
            'Fecha Activación',
            'Fecha Finalización',
            'Plazo Renting',
            'Tiempo En Sitio',
            'Tiempo Restante',
            'Días En Servicio',
            'Costo Diario',
            'Costo Días En Servicio',
        ]
        for col, header in enumerate(eq_headers):
            sheet_eq.write(2, col, header, th)

        row = 3
        for e in equipment_lines:
            sheet_eq.write(row, 0, e.business_line_name or '', td)
            sheet_eq.write(row, 1, e.product_name or '', td)
            sheet_eq.write(row, 2, e.inventory_plate or '', td)
            sheet_eq.write(row, 3, e.lot_name or '', td)
            _au_eq = (e.assigned_user_display_name or '').strip()
            sheet_eq.write(row, 4, _au_eq, td)
            sheet_eq.write_number(row, 5, float(e.cost_renting_total or 0.0), td_money)
            sheet_eq.write_number(row, 6, float(e.cost_additional or 0.0), td_money)
            sheet_eq.write(row, 7, str(e.entry_date) if e.entry_date else '', td)
            sheet_eq.write(row, 8, str(e.exit_date) if e.exit_date else '', td)
            sheet_eq.write(row, 9, e.reining_plazo or '', td)
            sheet_eq.write(row, 10, e.tiempo_en_sitio_display or '', td)
            sheet_eq.write(row, 11, e.tiempo_restante_display or '', td)
            sheet_eq.write_number(row, 12, int(e.days_in_service or 0), td_center)
            sheet_eq.write_number(row, 13, float(e.cost_daily or 0.0), td_money)
            sheet_eq.write_number(row, 14, float(e.cost_to_date or 0.0), td_money)
            row += 1

