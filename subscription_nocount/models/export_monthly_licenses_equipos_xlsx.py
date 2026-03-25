# -*- coding: utf-8 -*-
from odoo import models, _


class ExportMonthlyLicensesEquiposXlsx(models.AbstractModel):
    # Odoo/Pg limitan el nombre de tabla a 63 caracteres.
    # Si el _name es demasiado largo, Odoo falla al inicializar el modelo del reporte XLSX.
    _name = 'report.subscription_nocount.monthly_lic_eq_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Exportar Licencias y Equipos (Facturable mensual guardado) a Excel'

    def generate_xlsx_report(self, workbook, data, bills):
        if not bills:
            return
        billable = bills[0]

        # Datos guardados (no se recalcula con transientes de "en vivo")
        license_details = billable._get_export_saved_license_details()
        equipment_details = billable._get_export_saved_equipment_details()

        # Estilos
        h1 = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        th = workbook.add_format({
            'bold': True, 'bg_color': '#004f9f', 'font_color': 'white', 'border': 1,
            'align': 'center', 'valign': 'vcenter'
        })
        td = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        td_center = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'center'})
        td_money = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'right', 'num_format': '#,##0.00'})

        # Hoja: Licencias
        sheet_lic = workbook.add_worksheet(_('Licencias'))
        sheet_lic.write(0, 0, _('EXPORTACION LICENCIAS (FACTURABLE GUARDADO)'), h1)

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
        for l in license_details:
            sheet_lic.write(row, 0, l.business_line_name or '', td)
            sheet_lic.write(row, 1, l.product_name or '', td)
            sheet_lic.write(row, 2, l.lot_name or '', td)
            sheet_lic.write(row, 3, l.inventory_plate or '', td)
            if hasattr(l, 'assigned_user_name'):
                _au_ml = getattr(l, 'assigned_user_name', '') or ''
            else:
                _au_ml = (l.assigned_user_display_name or '').strip()
            sheet_lic.write(row, 4, _au_ml, td)
            sheet_lic.write(row, 5, l.license_service_name or '', td)
            sheet_lic.write_number(row, 6, float(l.cost_renting or 0.0), td_money)
            sheet_lic.write(row, 7, (l.currency_id.name if l.currency_id else '') or '', td)
            row += 1

        # Hoja: Equipos
        sheet_eq = workbook.add_worksheet(_('Equipos'))
        sheet_eq.write(0, 0, _('EXPORTACION EQUIPOS (FACTURABLE GUARDADO)'), h1)

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
        for e in equipment_details:
            sheet_eq.write(row, 0, e.business_line_name or '', td)
            sheet_eq.write(row, 1, e.product_name or '', td)
            sheet_eq.write(row, 2, e.inventory_plate or '', td)
            sheet_eq.write(row, 3, e.lot_name or '', td)
            _au_me = (e.assigned_user_display_name or '').strip()
            sheet_eq.write(row, 4, _au_me, td)
            sheet_eq.write_number(row, 5, float(e.cost_renting_total or 0.0), td_money)
            sheet_eq.write_number(row, 6, float(e.cost_additional or 0.0), td_money)
            sheet_eq.write(row, 7, str(e.entry_date) if e.entry_date else '', td)
            sheet_eq.write(row, 8, str(e.exit_date) if e.exit_date else '', td)
            sheet_eq.write(row, 9, e.reining_plazo or '', td)
            sheet_eq.write(row, 10, e.tiempo_en_sitio_display or '', td)
            sheet_eq.write(row, 11, e.tiempo_restante_display or '', td)
            sheet_eq.write(row, 12, int(e.days_in_service or 0), td_center)
            sheet_eq.write_number(row, 13, float(e.cost_daily or 0.0), td_money)
            sheet_eq.write_number(row, 14, float(e.cost_to_date or 0.0), td_money)
            row += 1

