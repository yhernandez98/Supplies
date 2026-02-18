# -*- coding: utf-8 -*-
"""
Script de debug para identificar qué módulo está intentando eliminar un lote
que está siendo referenciado por stock.lot.supply.line
"""
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class StockLot(models.Model):
    _inherit = 'stock.lot'
    
    def unlink(self):
        """Sobrescribir unlink para registrar qué módulo está intentando eliminar el lote"""
        for lot in self:
            # Verificar si el lote está siendo referenciado por stock.lot.supply.line
            if 'stock.lot.supply.line' in self.env:
                supply_lines = self.env['stock.lot.supply.line'].search([
                    ('related_lot_id', '=', lot.id)
                ])
                if supply_lines:
                    # Obtener el traceback para ver qué módulo está llamando a unlink
                    import traceback
                    tb = traceback.format_stack()
                    _logger.error('=' * 80)
                    _logger.error('🚨 INTENTO DE ELIMINAR LOTE QUE TIENE REFERENCIAS')
                    _logger.error('=' * 80)
                    _logger.error('Lote: %s (ID: %s)', lot.name, lot.id)
                    _logger.error('Producto: %s (ID: %s)', lot.product_id.name if lot.product_id else 'N/A', lot.product_id.id if lot.product_id else 'N/A')
                    _logger.error('Líneas de supply_line que referencian este lote: %s', len(supply_lines))
                    for sl in supply_lines:
                        _logger.error('  - ID: %s, lot_id: %s (ID: %s), product_id: %s', 
                                    sl.id, sl.lot_id.name, sl.lot_id.id, sl.product_id.name)
                    _logger.error('')
                    _logger.error('TRACEBACK (últimas 30 líneas):')
                    for line in tb[-30:]:
                        _logger.error(line.rstrip())
                    _logger.error('=' * 80)
        
        return super().unlink()
