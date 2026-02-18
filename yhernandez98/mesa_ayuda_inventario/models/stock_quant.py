# -*- coding: utf-8 -*-

from odoo import api, models


class StockQuant(models.Model):
    """Extender stock.quant para forzar recálculo de información del cliente cuando cambie la ubicación."""
    _inherit = 'stock.quant'

    def write(self, vals):
        """Forzar recálculo de customer_info cuando cambie la ubicación o la cantidad."""
        res = super().write(vals)
        
        # Si cambia la ubicación o la cantidad, forzar recálculo de customer_info
        if 'location_id' in vals or 'quantity' in vals:
            try:
                lot_ids = self.mapped('lot_id').filtered(lambda l: l.id)
                if lot_ids and hasattr(lot_ids, '_compute_customer_info'):
                    # Forzar recálculo de customer_info de forma segura
                    lot_ids._compute_customer_info()
            except Exception:
                # Si hay algún error, simplemente no hacer nada
                pass
        
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Forzar recálculo de customer_info cuando se crea un nuevo quant."""
        res = super().create(vals_list)
        
        # Obtener los lot_ids afectados
        try:
            lot_ids = res.mapped('lot_id').filtered(lambda l: l.id)
            if lot_ids and hasattr(lot_ids, '_compute_customer_info'):
                # Forzar recálculo de customer_info de forma segura
                lot_ids._compute_customer_info()
        except Exception:
            # Si hay algún error, simplemente no hacer nada
            pass
        
        return res

