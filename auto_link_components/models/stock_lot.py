# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model
    def create(self, vals):
        """
        Al crear un nuevo lote, buscar automáticamente otros lotes con el mismo nombre
        y crear las relaciones entre TODOS ellos
        """
        lot = super(StockLot, self).create(vals)
        
        # Solo procesar si el lote tiene nombre y producto
        if not lot.name or not lot.product_id:
            return lot
        
        # Buscar otros lotes con el mismo nombre pero diferentes productos
        other_lots = self.env['stock.lot'].search([
            ('name', '=', lot.name),
            ('id', '!=', lot.id),
            ('product_id', '!=', lot.product_id.id),
        ])
        
        if not other_lots:
            return lot
        
        # Crear relaciones bidireccionales entre TODOS los lotes
        all_lots = other_lots | lot
        self._create_full_mesh_relations(all_lots)
        
        return lot

    def _create_full_mesh_relations(self, lots):
        """
        Crea relaciones bidireccionales entre TODOS los lotes (malla completa)
        Cada lote verá a todos los demás en "Elementos asociados"
        """
        SupplyLine = self.env['stock.lot.supply.line']
        
        for lot_a in lots:
            for lot_b in lots:
                if lot_a.id == lot_b.id:
                    continue  # No vincular un lote consigo mismo
                
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

    def action_link_same_lot_components(self):
        """
        Acción manual para vincular componentes con el mismo número de lote
        """
        self.ensure_one()
        
        # Buscar otros lotes con el mismo nombre
        other_lots = self.env['stock.lot'].search([
            ('name', '=', self.name),
            ('id', '!=', self.id),
            ('product_id', '!=', self.product_id.id),
        ])
        
        if not other_lots:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin componentes'),
                    'message': _('No se encontraron otros productos con el lote %s') % self.name,
                    'type': 'warning',
                }
            }
        
        # Crear relaciones completas entre todos
        all_lots = other_lots | self
        self._create_full_mesh_relations(all_lots)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Relaciones creadas'),
                'message': _('Se vincularon %s componentes') % len(other_lots),
                'type': 'success',
            }
        }

    @api.model
    def action_mass_link_all_lots(self):
        """
        Vincula masivamente TODOS los lotes del sistema que compartan el mismo nombre
        Solo procesa lotes que tengan stock disponible
        """
        # Obtener todos los lotes que tienen stock
        all_lots = self.env['stock.lot'].search([
            ('product_qty', '>', 0)  # Solo lotes con stock disponible
        ])
        
        # Agrupar por nombre de lote
        lot_groups = {}
        for lot in all_lots:
            if lot.name not in lot_groups:
                lot_groups[lot.name] = []
            lot_groups[lot.name].append(lot)
        
        # Procesar solo grupos con más de un producto
        processed_groups = 0
        total_relations = 0
        skipped_lots = 0
        
        for lot_name, lots in lot_groups.items():
            if len(lots) < 2:
                continue  # Solo un producto con este lote, saltar
            
            # Verificar que sean productos diferentes
            product_ids = [lot.product_id.id for lot in lots]
            if len(set(product_ids)) < 2:
                continue  # Mismo producto repetido, saltar
            
            # Verificar que todos tengan stock antes de vincular
            lots_with_stock = [lot for lot in lots if lot.product_qty > 0]
            
            if len(lots_with_stock) < 2:
                skipped_lots += len(lots)
                continue  # No hay suficientes lotes con stock para vincular
            
            try:
                # Crear relaciones para este grupo
                self._create_full_mesh_relations(lots_with_stock)
                processed_groups += 1
                total_relations += len(lots_with_stock) * (len(lots_with_stock) - 1)
            except Exception as e:
                # Si falla la vinculación de un grupo, continuar con el siguiente
                skipped_lots += len(lots_with_stock)
                continue
        
        message = 'Se procesaron %s grupos de lotes y se crearon %s relaciones.' % (processed_groups, total_relations)
        if skipped_lots > 0:
            message += ' Se omitieron %s lotes sin stock o con errores.' % skipped_lots
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vinculacion masiva completada'),
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }
