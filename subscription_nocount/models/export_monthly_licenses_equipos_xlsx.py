# -*- coding: utf-8 -*-
from odoo import models, _

from .export_licenses_equipos_columns import (
    get_license_columns_from_export_data,
    get_equipment_columns_from_export_data,
    _val_monthly_lic,
    _val_monthly_eq,
    LICENSE_XLSX_NUMBER_KEYS,
    EQUIPMENT_XLSX_MONEY_KEYS,
    EQUIPMENT_XLSX_INT_KEYS,
)


class ExportMonthlyLicensesEquiposXlsx(models.AbstractModel):
    _name = 'report.subscription_nocount.monthly_lic_eq_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Exportar Licencias y Equipos (Facturable mensual guardado) a Excel'

    def _write_license_cell(self, sheet, row, col, key, value, td, td_money, td_center):
        if key in LICENSE_XLSX_NUMBER_KEYS:
            sheet.write_number(row, col, float(value), td_money)
        else:
            sheet.write(row, col, value, td)

    def _write_equipment_cell(self, sheet, row, col, key, value, td, td_money, td_center):
        if key in EQUIPMENT_XLSX_MONEY_KEYS:
            sheet.write_number(row, col, float(value), td_money)
        elif key in EQUIPMENT_XLSX_INT_KEYS:
            sheet.write_number(row, col, int(value), td_center)
        else:
            sheet.write(row, col, value, td)

    def generate_xlsx_report(self, workbook, data, bills):
        if not bills:
            return
        billable = bills[0]

        license_details = billable._get_export_saved_license_details()
        equipment_details = billable._get_export_saved_equipment_details()

        lic_cols = get_license_columns_from_export_data(data)
        eq_cols = get_equipment_columns_from_export_data(data)

        h1 = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        th = workbook.add_format({
            'bold': True, 'bg_color': '#004f9f', 'font_color': 'white', 'border': 1,
            'align': 'center', 'valign': 'vcenter'
        })
        td = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        td_center = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'center'})
        td_money = workbook.add_format({'border': 1, 'valign': 'vcenter', 'align': 'right', 'num_format': '#,##0.00'})

        sheet_lic = workbook.add_worksheet(_('Licencias'))
        sheet_lic.write(0, 0, _('EXPORTACION LICENCIAS (FACTURABLE GUARDADO)'), h1)
        if lic_cols:
            for col, (_key, header) in enumerate(lic_cols):
                sheet_lic.write(2, col, header, th)
            row = 3
            for l in license_details:
                for col, (key, _h) in enumerate(lic_cols):
                    val = _val_monthly_lic(l, key)
                    self._write_license_cell(sheet_lic, row, col, key, val, td, td_money, td_center)
                row += 1
            if not license_details:
                sheet_lic.merge_range(3, 0, 3, max(len(lic_cols) - 1, 0), _('Sin datos'), td_center)
        else:
            sheet_lic.write(2, 0, _('No se seleccionaron columnas para Licencias.'), td)

        sheet_eq = workbook.add_worksheet(_('Equipos'))
        sheet_eq.write(0, 0, _('EXPORTACION EQUIPOS (FACTURABLE GUARDADO)'), h1)
        if eq_cols:
            for col, (_key, header) in enumerate(eq_cols):
                sheet_eq.write(2, col, header, th)
            row = 3
            for e in equipment_details:
                for col, (key, _h) in enumerate(eq_cols):
                    val = _val_monthly_eq(e, key)
                    self._write_equipment_cell(sheet_eq, row, col, key, val, td, td_money, td_center)
                row += 1
            if not equipment_details:
                sheet_eq.merge_range(3, 0, 3, max(len(eq_cols) - 1, 0), _('Sin datos'), td_center)
        else:
            sheet_eq.write(2, 0, _('No se seleccionaron columnas para Equipos.'), td)
