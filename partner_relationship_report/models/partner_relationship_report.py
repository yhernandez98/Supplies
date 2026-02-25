# -*- coding: utf-8 -*-
from odoo import models

class PartnerRelationshipReportXlsx(models.AbstractModel):
    _name = 'report.partner_relationship_report.partner_rel_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte de Relaciones en Excel (OCA)'

    def generate_xlsx_report(self, workbook, data, wizard):
        """
        Columnas:
            Tipo | Serial | Producto | Producto principal | Serial principal
        Filtrado por partner y SOLO lotes con asociados válidos.
        """
        lines = wizard.get_report_lines()
        partner = wizard.partner_id

        sheet = workbook.add_worksheet('Relaciones')

        # Estilos
        h1 = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        th = workbook.add_format({'bold': True, 'bg_color': '#004f9f', 'font_color': 'white', 'border': 1, 'align': 'center'})
        td = workbook.add_format({'border': 1})
        td_bold = workbook.add_format({'border': 1, 'bold': True})

        # Encabezado
        sheet.merge_range(1, 0, 1, 4, 'RELACIÓN DE PRODUCTOS Y ASOCIADOS', h1)
        sheet.write(3, 0, 'EMPRESA:', th);      sheet.write(3, 1, partner.display_name or '')
        sheet.write(4, 0, 'NIT:', th);          sheet.write(4, 1, partner.vat or '')
        sheet.write(5, 0, 'CORREO:', th);       sheet.write(5, 1, partner.email or '')
        sheet.write(6, 0, 'TELÉFONO:', th);     sheet.write(6, 1, partner.phone or '')
        sheet.write(3, 3, 'FECHA CORTE:', th);  sheet.write(3, 4, wizard._get_today_str())

        # Cabecera de tabla
        start = 8
        headers = [
            'Serial', 'Modelo', 'Código de facturación', 'Cantidad',
            'Producto', 'Producto principal', 'Serial principal'
        ]
        for col, name in enumerate(headers):
            sheet.write(start, col, name, th)

        row = start
        for grp in lines:
            # Fila del principal
            row += 1
            sheet.write(row, 0, grp['principal_serial'], td)
            sheet.write(row, 1, grp['principal_model'], td)
            sheet.write(row, 2, grp['principal_billing_code'], td)
            sheet.write_number(row, 3, grp['principal_qty'], td) 
            sheet.write(row, 4, grp['principal_product'], td)
            sheet.write(row, 5, grp['principal_product'], td)
            sheet.write(row, 6, grp['principal_serial'], td)

            # Filas de asociados
            for ln in grp['lines']:
                row += 1
                sheet.write(row, 0, ln['serial'], td)
                sheet.write(row, 1, ln['model'], td)
                sheet.write(row, 2, ln['billing_code'], td)
                sheet.write_number(row, 3, ln['qty'], td) 
                sheet.write(row, 4, ln['product'], td)
                sheet.write(row, 5, grp['principal_product'], td)
                sheet.write(row, 6, grp['principal_serial'], td)

        row += 2
        sheet.write(row, 0, 'OBSERVACIONES:', th)
        sheet.merge_range(row + 1, 0, row + 3, 6, (wizard.observation or ''), td)

        # Anchos
        sheet.set_column('A:A', 22)  # Serial
        sheet.set_column('B:B', 26)  # Modelo
        sheet.set_column('C:C', 26)  # Código de facturación
        sheet.set_column('D:D', 12)  # Cantidad
        sheet.set_column('E:E', 50)  # Producto
        sheet.set_column('F:F', 50)  # Producto principal
        sheet.set_column('G:G', 22)  # Serial principal