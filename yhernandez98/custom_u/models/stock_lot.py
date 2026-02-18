# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    related_partner_id = fields.Many2one(
        "res.partner",
        string="Contacto Relacionado",
        help="Contacto/cliente al que está asignado este producto serializado.",
        index=True,
    )

    def write(self, vals):
        """Propaga el contacto a todos los elementos relacionados (componentes, periféricos, complementos)"""
        if 'related_partner_id' in vals:
            partner_id = vals.get('related_partner_id')
            for lot in self:
                # Si se está asignando un contacto (no es False/None)
                if partner_id:
                    # Obtener todos los lotes relacionados a través de las líneas de suministro
                    related_lots = lot._get_related_lots()
                    # Asignar el mismo contacto a todos los lotes relacionados
                    if related_lots:
                        related_lots.write({'related_partner_id': partner_id})
                # Si se está quitando el contacto, también quitarlo de los relacionados
                else:
                    related_lots = lot._get_related_lots()
                    related_lots.write({'related_partner_id': False})

        return super().write(vals)

    def _get_related_lots(self, visited=None):
        """Obtiene todos los lotes relacionados a este lote (componentes, periféricos, complementos)"""
        if visited is None:
            visited = set()
        
        # Evitar recursión infinita
        if self.id in visited:
            return self.env['stock.lot']
        
        visited.add(self.id)
        related_lots = self.env['stock.lot']
        
        # Buscar lotes que tienen este lote como principal
        lots_as_components = self.env['stock.lot'].search([
            ('principal_lot_id', '=', self.id)
        ])
        related_lots |= lots_as_components
        
        # Buscar lotes a través de las líneas de suministro
        if hasattr(self, 'lot_supply_line_ids'):
            for supply_line in self.lot_supply_line_ids:
                if supply_line.related_lot_id and supply_line.related_lot_id.id not in visited:
                    related_lots |= supply_line.related_lot_id
                    # También obtener los lotes relacionados de este lote (recursivo)
                    sub_related = supply_line.related_lot_id._get_related_lots(visited)
                    related_lots |= sub_related
        
        return related_lots

