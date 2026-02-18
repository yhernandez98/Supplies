# -*- coding: utf-8 -*-
import base64
import io
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import xlsxwriter


class LotLocationReportWizard(models.TransientModel):
    _name = 'lot.location.report.wizard'
    _description = 'Wizard para generar reporte de lotes y ubicaciones'

    # Filtros de fecha
    date_from = fields.Date(
        string='Fecha Desde',
        default=fields.Date.context_today,
        help='Fecha inicial para filtrar los lotes'
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        default=fields.Date.context_today,
        help='Fecha final para filtrar los lotes'
    )

    # Filtros de ubicación
    location_ids = fields.Many2many(
        'stock.location',
        string='Ubicaciones',
        domain=[('usage', '=', 'internal')],
        help='Filtrar por ubicaciones específicas (dejar vacío para todas)'
    )

    # Filtros de producto
    product_ids = fields.Many2many(
        'product.product',
        string='Productos',
        domain=[('type', 'in', ['product', 'consu'])],
        help='Filtrar por productos específicos (dejar vacío para todos)'
    )

    # Filtros adicionales
    include_zero_stock = fields.Boolean(
        string='Incluir Stock Cero',
        default=False,
        help='Incluir lotes con cantidad 0'
    )
    only_tracked_lots = fields.Boolean(
        string='Solo Lotes con Trazabilidad',
        default=True,
        help='Mostrar solo lotes de productos con trazabilidad'
    )

    # Campos para el archivo generado
    excel_file = fields.Binary(
        string='Archivo Excel',
        readonly=True
    )
    excel_filename = fields.Char(
        string='Nombre del Archivo',
        readonly=True
    )

    def _get_lot_field_safely(self, lot, field_name, default=''):
        """Obtiene un campo del lote de forma segura, manejando campos que pueden no existir"""
        if hasattr(lot, field_name):
            value = getattr(lot, field_name)
            if value and hasattr(value, 'strftime'):
                try:
                    return value.strftime('%Y-%m-%d')
                except:
                    return str(value)
            return str(value) if value else default
        return default

    def _get_lot_data(self):
        """Obtiene los datos de lotes según los filtros aplicados"""
        domain = []
        
        # Filtro por fechas (basado en fecha de creación del lote)
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        # Filtro por productos
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        elif self.only_tracked_lots:
            domain.append(('product_id.tracking', '!=', 'none'))
        
        # Obtener todos los lotes que cumplan los criterios
        lots = self.env['stock.lot'].search(domain)
        
        # Preparar datos para el reporte
        lot_data = []
        for lot in lots:
            # Obtener ubicaciones con stock para este lote
            quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0 if not self.include_zero_stock else -999999)
            ])
            
            # Filtrar por ubicaciones si se especificaron
            if self.location_ids:
                quants = quants.filtered(lambda q: q.location_id in self.location_ids)
            
            if quants or self.include_zero_stock:
                for quant in quants:
                    # Obtener información de seriales relacionados
                    related_serials = []
                    if hasattr(lot, 'lot_supply_line_ids'):
                        for supply_line in lot.lot_supply_line_ids:
                            if supply_line.related_lot_id:
                                related_serials.append(supply_line.related_lot_id.name)
                    
                    # Obtener documento origen (último movimiento de entrada)
                    origin_document = ''
                    last_move = self.env['stock.move.line'].search([
                        ('lot_id', '=', lot.id),
                        ('state', '=', 'done')
                    ], order='date desc', limit=1)
                    if last_move and last_move.picking_id:
                        origin_document = last_move.picking_id.origin or last_move.picking_id.name
                    
                    lot_data.append({
                        'warehouse_name': quant.location_id.warehouse_id.name if quant.location_id.warehouse_id else '',
                        'location_name': quant.location_id.complete_name,
                        'product_name': lot.product_id.name,
                        'serial': lot.name,
                        'inventory_plate': self._get_lot_field_safely(lot, 'inventory_plate'),
                        'security_plate': self._get_lot_field_safely(lot, 'security_plate'),
                        'billing_code': self._get_lot_field_safely(lot, 'billing_code'),
                        'asset_category': lot.product_id.product_tmpl_id.asset_category_id.name if hasattr(lot.product_id.product_tmpl_id, 'asset_category_id') and lot.product_id.product_tmpl_id.asset_category_id else '',
                        'related_serials': ', '.join(related_serials) if related_serials else '',
                        'origin_document': origin_document,
                        'effective_date': last_move.date.strftime('%Y-%m-%d %H:%M:%S') if last_move and last_move.date else lot.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                    })
        
        return lot_data

    def generate_excel_report(self):
        """Genera el archivo Excel con los datos de lotes"""
        # Obtener datos
        lot_data = self._get_lot_data()
        
        if not lot_data:
            raise UserError(_('No se encontraron datos para generar el reporte con los filtros aplicados.'))
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Reporte Lotes y Ubicaciones')
        
        # Definir formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#366092',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00'
        })
        
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'num_format': 'yyyy-mm-dd'
        })
        
        # Definir encabezados
        headers = [
            'Almacén',
            'Ubicación',
            'Producto',
            'Serial',
            'Placa de Inventario',
            'Placa de Seguridad',
            'Código de Facturación',
            'Categoría de Activo',
            'Seriales Relacionados',
            'Documento Origen',
            'Fecha Efectiva'
        ]
        
        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Ajustar ancho de columnas
        column_widths = [20, 30, 25, 20, 18, 18, 18, 20, 25, 20, 18]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # Escribir datos
        for row, data in enumerate(lot_data, 1):
            worksheet.write(row, 0, data['warehouse_name'], data_format)
            worksheet.write(row, 1, data['location_name'], data_format)
            worksheet.write(row, 2, data['product_name'], data_format)
            worksheet.write(row, 3, data['serial'], data_format)
            worksheet.write(row, 4, data['inventory_plate'], data_format)
            worksheet.write(row, 5, data['security_plate'], data_format)
            worksheet.write(row, 6, data['billing_code'], data_format)
            worksheet.write(row, 7, data['asset_category'], data_format)
            worksheet.write(row, 8, data['related_serials'], data_format)
            worksheet.write(row, 9, data['origin_document'], data_format)
            worksheet.write(row, 10, data['effective_date'], data_format)
        
        # Agregar información del reporte
        info_row = len(lot_data) + 3
        worksheet.write(info_row, 0, 'Información del Reporte:', header_format)
        worksheet.write(info_row + 1, 0, f'Fecha de generación: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        worksheet.write(info_row + 2, 0, f'Total de registros: {len(lot_data)}')
        worksheet.write(info_row + 3, 0, f'Filtros aplicados:')
        worksheet.write(info_row + 4, 0, f'  - Fecha desde: {self.date_from or "No especificada"}')
        worksheet.write(info_row + 5, 0, f'  - Fecha hasta: {self.date_to or "No especificada"}')
        worksheet.write(info_row + 6, 0, f'  - Ubicaciones: {len(self.location_ids) if self.location_ids else "Todas"}')
        worksheet.write(info_row + 7, 0, f'  - Productos: {len(self.product_ids) if self.product_ids else "Todos"}')
        worksheet.write(info_row + 8, 0, f'  - Incluir stock cero: {"Sí" if self.include_zero_stock else "No"}')
        worksheet.write(info_row + 9, 0, f'  - Solo con trazabilidad: {"Sí" if self.only_tracked_lots else "No"}')
        
        # Cerrar workbook
        workbook.close()
        output.seek(0)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'Reporte_Lotes_Ubicaciones_{timestamp}.xlsx'
        
        # Actualizar el wizard con el archivo generado
        self.write({
            'excel_file': base64.b64encode(output.read()),
            'excel_filename': filename
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reporte Generado'),
            'res_model': 'lot.location.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'excel_generated': True}
        }

    def action_download_excel(self):
        """Acción para descargar el archivo Excel"""
        if not self.excel_file:
            raise UserError(_('No hay archivo Excel generado para descargar.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=lot.location.report.wizard&id={self.id}&field=excel_file&filename_field=excel_filename&download=true',
            'target': 'new',
        }

