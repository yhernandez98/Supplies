# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    """Extender Sale Order Line para verificar stock cuando se agregan productos."""
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir creación para verificar stock cuando se agregan productos."""
        lines = super().create(vals_list)
        
        # Verificar si la orden viene de un Lead y crear alertas automáticamente
        for line in lines:
            if line.order_id and line.order_id.opportunity_id and line.order_id.state == 'draft':
                try:
                    # Forzar recálculo del stock en la orden
                    line.order_id._compute_stock_availability()
                    line.order_id.flush_recordset()
                    
                    # Crear alertas automáticamente
                    line.order_id._create_purchase_alerts_automatically()
                except Exception as e:
                    _logger.error("Error en verificación automática para línea %s: %s", line.id, str(e))
        
        return lines
    
    def write(self, vals):
        """Sobrescribir escritura para verificar stock cuando se modifican productos."""
        result = super().write(vals)
        
        # Si se modificó el producto o la cantidad, verificar stock
        if 'product_id' in vals or 'product_uom_qty' in vals:
            for line in self:
                if line.order_id and line.order_id.opportunity_id and line.order_id.state == 'draft':
                    try:
                        line.order_id._compute_stock_availability()
                        line.order_id.flush_recordset()
                        line.order_id._create_purchase_alerts_automatically()
                    except Exception as e:
                        _logger.error("Error en verificación automática para línea %s: %s", line.id, str(e))
        
        return result

