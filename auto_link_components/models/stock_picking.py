# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_auto_link_components_by_lot(self):
        """
        Vincula automáticamente TODOS los productos que compartan el mismo número de lote
        """
        self.ensure_one()
        
        # Agrupar movimientos por número de lote
        lot_groups = {}
        
        for move in self.move_ids_without_package:
            if not move.lot_ids:
                continue
                
            for lot in move.lot_ids:
                lot_name = lot.name
                if lot_name not in lot_groups:
                    lot_groups[lot_name] = []
                lot_groups[lot_name].append(lot)
        
        # Procesar cada grupo de lote
        created_relations = 0
        for lot_name, lots in lot_groups.items():
            if len(lots) < 2:
                continue  # No hay suficientes items para relacionar
            
            # Crear relaciones bidireccionales entre TODOS los lotes del grupo
            created_relations += self._create_full_mesh_relations(lots)
        
        if created_relations > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Relaciones creadas'),
                    'message': _('Se crearon %s relaciones automáticamente.') % created_relations,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin relaciones'),
                    'message': _('No se encontraron productos con el mismo lote para vincular.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def _create_full_mesh_relations(self, lots):
        """
        Crea relaciones bidireccionales entre TODOS los lotes
        """
        SupplyLine = self.env['stock.lot.supply.line']
        created = 0
        
        for lot_a in lots:
            for lot_b in lots:
                if lot_a.id == lot_b.id:
                    continue
                
                # Verificar si la relación ya existe
                existing = SupplyLine.search([
                    ('lot_id', '=', lot_a.id),
                    ('related_lot_id', '=', lot_b.id),
                ], limit=1)
                
                if not existing:
                    SupplyLine.create({
                        'lot_id': lot_a.id,
                        'product_id': lot_b.product_id.id,
                        'quantity': 1,
                        'related_lot_id': lot_b.id,
                        'uom_id': lot_b.product_id.uom_id.id,
                        'item_type': 'component',
                    })
                    created += 1
        
        return created