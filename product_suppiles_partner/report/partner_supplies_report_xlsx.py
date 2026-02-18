# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, _
from odoo.exceptions import UserError


class PartnerSuppliesReportXlsx(models.AbstractModel):
    _name = 'report.product_suppiles_partner.partner_supplies_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte de Productos Serializados por Contacto en Excel'

    def generate_xlsx_report(self, workbook, data, wizard):
        """Genera el reporte Excel con los productos serializados del contacto"""
        partner = self.env['res.partner'].browse(data.get('partner_id'))
        if not partner:
            raise UserError(_('Contacto no encontrado'))
        
        include_components = data.get('include_components', True)
        observation = data.get('observation', '')
        
        # Crear hoja de trabajo
        sheet = workbook.add_worksheet('Productos Serializados')
        
        # Formatos
        h1 = workbook.add_format({
            'bold': True, 
            'font_size': 14, 
            'align': 'center',
            'bg_color': '#366092',
            'font_color': 'white'
        })
        h2 = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#D9E1F2',
            'border': 1
        })
        th = workbook.add_format({
            'bold': True, 
            'bg_color': '#004f9f', 
            'font_color': 'white', 
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        td = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        td_center = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        td_number = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0'
        })
        
        # Encabezado principal
        sheet.merge_range(0, 0, 0, 6, 'REPORTE DE PRODUCTOS SERIALIZADOS', h1)
        
        # Información del contacto
        row = 2
        sheet.write(row, 0, 'CONTACTO:', h2)
        sheet.write(row, 1, partner.name or '')
        row += 1
        
        sheet.write(row, 0, 'NIT:', h2)
        sheet.write(row, 1, partner.vat or '')
        sheet.write(row, 3, 'FECHA CORTE:', h2)
        sheet.write(row, 4, date.today().strftime('%d/%m/%Y'))
        row += 1
        
        sheet.write(row, 0, 'CORREO:', h2)
        sheet.write(row, 1, partner.email or '')
        sheet.write(row, 3, 'TELÉFONO:', h2)
        sheet.write(row, 4, partner.phone or '')
        row += 1
        
        sheet.write(row, 0, 'DIRECCIÓN:', h2)
        address = partner.contact_address or ''
        sheet.write(row, 1, address)
        row += 2
        
        # Título de la tabla
        sheet.write(row, 0, 'EQUIPOS ASIGNADOS', h2)
        row += 1
        
        # Encabezados de la tabla
        headers = ['CÓDIGO SERIAL', 'PRODUCTO', 'TIPO', 'UBICACIÓN', 'CANTIDAD', 'OBSERVACIONES']
        col_widths = [18, 35, 20, 25, 12, 30]
        
        for col, header in enumerate(headers):
            sheet.write(row, col, header, th)
            sheet.set_column(col, col, col_widths[col])
        
        row += 1
        
        # Obtener lotes según configuración
        if include_components:
            lots = partner.all_lot_ids
        else:
            lots = partner.main_lot_ids
        
        # Datos de los lotes
        for lot in lots:
            # Determinar tipo de item
            item_type = 'Principal'
            if hasattr(lot, 'lot_supply_line_ids'):
                # Buscar si este lote es un componente
                parent_lots = self.env['stock.lot'].search([
                    ('lot_supply_line_ids.related_lot_id', '=', lot.id)
                ])
                if parent_lots:
                    # Buscar el tipo en la línea de suministro
                    supply_line = self.env['stock.lot.supply.line'].search([
                        ('related_lot_id', '=', lot.id)
                    ], limit=1)
                    if supply_line:
                        type_map = {
                            'component': 'Componente',
                            'peripheral': 'Periférico',
                            'complement': 'Complemento'
                        }
                        item_type = type_map.get(supply_line.item_type, 'Componente')
            
            # Obtener ubicación actual
            location_name = ''
            if hasattr(lot, 'current_location_id') and lot.current_location_id:
                location_name = lot.current_location_id.complete_name
            else:
                # Buscar en quants
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal')
                ], limit=1)
                if quant:
                    location_name = quant.location_id.complete_name
            
            # Escribir datos
            sheet.write(row, 0, lot.name or '', td)
            sheet.write(row, 1, lot.product_id.display_name or '', td)
            sheet.write(row, 2, item_type, td_center)
            sheet.write(row, 3, location_name, td)
            sheet.write_number(row, 4, 1, td_number)
            
            # Observaciones adicionales del lote
            lot_notes = ''
            if hasattr(lot, 'ref') and lot.ref:
                lot_notes = f"Ref: {lot.ref}"
            sheet.write(row, 5, lot_notes, td)
            
            row += 1
        
        # Si no hay lotes
        if not lots:
            sheet.merge_range(row, 0, row, 5, 
                            'No hay productos serializados asignados a este contacto.', 
                            td_center)
            row += 1
        
        # Observaciones generales
        if observation:
            row += 2
            sheet.write(row, 0, 'OBSERVACIONES:', h2)
            row += 1
            sheet.merge_range(row, 0, row + 2, 5, observation, td)
            row += 3
        
        # Resumen
        row += 1
        sheet.write(row, 0, 'RESUMEN:', h2)
        row += 1
        sheet.write(row, 0, 'Total Seriales Principales:', td)
        sheet.write_number(row, 1, len(partner.main_lot_ids), td_number)
        row += 1
        
        if include_components:
            sheet.write(row, 0, 'Total (Incluyendo Componentes):', td)
            sheet.write_number(row, 1, len(partner.all_lot_ids), td_number)

