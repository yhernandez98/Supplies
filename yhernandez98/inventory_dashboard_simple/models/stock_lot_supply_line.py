# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class StockLotSupplyLine(models.Model):
    """Extender stock.lot.supply.line para recalcular has_excluded_supply_elements cuando cambien las líneas."""
    _inherit = 'stock.lot.supply.line'

    def write(self, vals):
        """Recalcular has_excluded_supply_elements cuando cambien las líneas de suministro."""
        res = super().write(vals)
        
        # Recalcular has_excluded_supply_elements en los lotes afectados
        try:
            lot_ids = self.mapped('lot_id').filtered(lambda l: l.id)
            if lot_ids and hasattr(lot_ids, '_compute_has_excluded_supply_elements'):
                lot_ids.invalidate_cache(['has_excluded_supply_elements'])
                lot_ids._compute_has_excluded_supply_elements()
        except Exception as e:
            _logger.warning('Error al recalcular has_excluded_supply_elements en write: %s', str(e))
        
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Recalcular has_excluded_supply_elements cuando se creen nuevas líneas de suministro."""
        res = super().create(vals_list)
        
        # Recalcular has_excluded_supply_elements en los lotes afectados
        try:
            lot_ids = res.mapped('lot_id').filtered(lambda l: l.id)
            if lot_ids and hasattr(lot_ids, '_compute_has_excluded_supply_elements'):
                lot_ids.invalidate_cache(['has_excluded_supply_elements'])
                lot_ids._compute_has_excluded_supply_elements()
        except Exception as e:
            _logger.warning('Error al recalcular has_excluded_supply_elements en create: %s', str(e))
        
        return res

    def unlink(self):
        """Recalcular has_excluded_supply_elements cuando se eliminen líneas de suministro."""
        lot_ids = self.mapped('lot_id').filtered(lambda l: l.id)
        res = super().unlink()
        
        # Recalcular has_excluded_supply_elements en los lotes afectados
        try:
            if lot_ids and hasattr(lot_ids, '_compute_has_excluded_supply_elements'):
                lot_ids.invalidate_cache(['has_excluded_supply_elements'])
                lot_ids._compute_has_excluded_supply_elements()
        except Exception as e:
            _logger.warning('Error al recalcular has_excluded_supply_elements en unlink: %s', str(e))
        
        return res
