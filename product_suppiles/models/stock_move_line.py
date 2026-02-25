# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from odoo.tools import float_round, float_compare
import logging

from collections import defaultdict
from odoo.addons.stock_account.models.stock_move_line import (
    StockMoveLine as StockAccountMoveLine,
)

_logger = logging.getLogger(__name__)
class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    supply_kind = fields.Selection(
        related="move_id.supply_kind", store=True, readonly=True
    )

    purchase_tracking_ref = fields.Char(
        related="move_id.purchase_tracking_ref",
        store=False,
        readonly=True,
    )
    
    # Campos para mostrar elementos asociados en columnas
    associated_components = fields.Char(
        string='Componentes',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de componentes asociados'
    )
    
    associated_peripherals = fields.Char(
        string='Periféricos',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de periféricos asociados'
    )
    
    associated_complements = fields.Char(
        string='Complementos',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de complementos asociados'
    )
    
    @api.depends('lot_id', 'lot_id.lot_supply_line_ids', 'lot_id.lot_supply_line_ids.related_lot_id', 
                 'lot_id.lot_supply_line_ids.item_type', 'lot_id.lot_supply_line_ids.related_lot_id.name')
    def _compute_associated_elements(self):
        """Calcular elementos asociados agrupados por tipo para mostrar en columnas."""
        for line in self:
            line.associated_components = ''
            line.associated_peripherals = ''
            line.associated_complements = ''
            
            # Solo procesar si es un producto principal y tiene lote
            if not line.lot_id or line.supply_kind != 'parent':
                continue
            
            if not hasattr(line.lot_id, 'lot_supply_line_ids') or not line.lot_id.lot_supply_line_ids:
                continue
            
            # Agrupar elementos asociados por tipo
            components = []
            peripherals = []
            complements = []
            
            for supply_line in line.lot_id.lot_supply_line_ids:
                if not supply_line.related_lot_id:
                    continue
                
                serial_name = supply_line.related_lot_id.name or ''
                if not serial_name:
                    continue
                
                if supply_line.item_type == 'component':
                    components.append(serial_name)
                elif supply_line.item_type == 'peripheral':
                    peripherals.append(serial_name)
                elif supply_line.item_type == 'complement':
                    complements.append(serial_name)
                elif supply_line.item_type in ('monitor', 'ups'):
                    # Monitores y UPS se muestran como periféricos
                    peripherals.append(serial_name)
            
            # Unir los números de serie con comas
            line.associated_components = ', '.join(components) if components else ''
            line.associated_peripherals = ', '.join(peripherals) if peripherals else ''
            line.associated_complements = ', '.join(complements) if complements else ''

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe create para asegurar que los movimientos hijos usen solo el lote relacionado.
        Elimina líneas duplicadas que no tienen el lote relacionado correcto.
        CORRECCIÓN: Asegura que solo haya UNA línea por producto relacionado.
        """
        lines = super().create(vals_list)
        
        # Procesar cada línea creada
        for line in lines:
            if line.move_id and line.move_id.internal_parent_move_id:
                # Es un movimiento hijo, verificar que use el lote relacionado correcto
                parent_move = line.move_id.internal_parent_move_id
                
                # Obtener el lote principal del movimiento padre
                parent_move_lines = parent_move.move_line_ids.filtered(
                    lambda ml: ml.lot_id and ml.lot_id.exists() and ml.supply_kind == "parent"
                )
                if parent_move_lines and len(parent_move_lines) > 0:
                    principal_lot = parent_move_lines[0].lot_id
                    
                    # Buscar el lote relacionado correcto para este producto
                    if principal_lot and principal_lot.exists() and hasattr(principal_lot, 'lot_supply_line_ids'):
                        supply_lines = principal_lot.lot_supply_line_ids.filtered(
                            lambda sl: sl.product_id.id == line.product_id.id and 
                                     sl.related_lot_id and sl.related_lot_id.exists()
                        )
                        if supply_lines and len(supply_lines) > 0:
                            related_lot = supply_lines[0].related_lot_id
                            
                            # CORRECCIÓN CRÍTICA: Eliminar TODAS las otras líneas del mismo movimiento y producto
                            # Esto asegura que solo haya UNA línea por producto relacionado
                            # CORRECCIÓN: NO eliminar líneas que ya tienen el lote relacionado correcto
                            # CORRECCIÓN: Verificar que las líneas existen antes de eliminarlas
                            other_lines = line.move_id.move_line_ids.filtered(
                                lambda ml: ml.id and ml.id != line.id and 
                                         ml.product_id.id == line.product_id.id and
                                         (not ml.lot_id or not ml.lot_id.exists() or ml.lot_id.id != related_lot.id)
                            )
                            if other_lines:
                                # Verificar que las líneas realmente existen antes de procesarlas
                                existing_other_lines = other_lines.filtered(lambda ml: ml.id and ml.exists())
                                if existing_other_lines:
                                    # Sumar las cantidades de las líneas duplicadas antes de eliminarlas
                                    total_qty = sum(existing_other_lines.mapped('quantity'))
                                    # Eliminar solo las líneas que NO tienen el lote relacionado correcto
                                    existing_other_lines.unlink()
                                    # Actualizar la cantidad de la línea correcta si es necesario
                                    if total_qty > 0 and line.id and line.exists():
                                        if line.quantity:
                                            line.quantity = line.quantity + total_qty
                                        else:
                                            line.quantity = total_qty
                            
                            # Si la línea creada no tiene el lote relacionado correcto, actualizarla
                            if not line.lot_id or line.lot_id.id != related_lot.id:
                                line.lot_id = related_lot.id
                            
                            # Asegurar que la cantidad sea correcta (no duplicada)
                            # La cantidad debe ser la del movimiento, no duplicada
                            if line.quantity > line.move_id.product_uom_qty:
                                line.quantity = line.move_id.product_uom_qty
        
        return lines

    def write(self, vals):
        """
        Sobrescribe write para asegurar que los movimientos hijos mantengan el lote relacionado correcto.
        """
        result = super().write(vals)
        
        # Si se está actualizando el lot_id o se está creando una nueva línea
        for line in self:
            if line.move_id and line.move_id.internal_parent_move_id:
                # Es un movimiento hijo, verificar que use el lote relacionado correcto
                parent_move = line.move_id.internal_parent_move_id
                
                # Obtener el lote principal del movimiento padre
                parent_move_lines = parent_move.move_line_ids.filtered(
                    lambda ml: ml.lot_id and ml.lot_id.exists() and ml.supply_kind == "parent"
                )
                if parent_move_lines and len(parent_move_lines) > 0:
                    principal_lot = parent_move_lines[0].lot_id
                    
                    # Buscar el lote relacionado correcto para este producto
                    if principal_lot and principal_lot.exists() and hasattr(principal_lot, 'lot_supply_line_ids'):
                        supply_lines = principal_lot.lot_supply_line_ids.filtered(
                            lambda sl: sl.product_id.id == line.product_id.id and 
                                     sl.related_lot_id and sl.related_lot_id.exists()
                        )
                        if supply_lines and len(supply_lines) > 0:
                            related_lot = supply_lines[0].related_lot_id
                            
                            # Si la línea no tiene el lote relacionado correcto, actualizarla
                            if not line.lot_id or line.lot_id.id != related_lot.id:
                                line.lot_id = related_lot.id
                            
                            # Eliminar otras líneas del mismo movimiento que no tengan el lote relacionado correcto
                            other_lines = line.move_id.move_line_ids.filtered(
                                lambda ml: ml.id != line.id and 
                                         ml.product_id.id == line.product_id.id and
                                         (not ml.lot_id or ml.lot_id.id != related_lot.id)
                            )
                            if other_lines:
                                other_lines.unlink()
        
        return result

    @api.model
    def _ensure_component_lot_ids_for_picking(self, picking):
        """
        Para devoluciones/salidas: asigna lot_id a líneas de componentes que aún no lo tienen,
        usando el lote principal del picking y lot_supply_line_ids.related_lot_id.
        Así todas las líneas quedan con lot_id y la consolidación puede detectar duplicados.
        """
        if not picking or not picking.exists() or not picking.move_line_ids:
            return
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        principal_lines = picking_lines.filtered(
            lambda ml: getattr(ml, "supply_kind", False) == "parent" and ml.lot_id and ml.lot_id.exists()
        )
        if not principal_lines:
            return
        principal_lots = principal_lines.mapped("lot_id")
        for ml in picking_lines:
            if not ml.product_id or ml.product_id.tracking == "none" or ml.lot_id:
                continue
            if getattr(ml, "supply_kind", False) == "parent":
                continue
            related_lot = None
            if ml.move_id and ml.move_id.internal_parent_move_id:
                parent_move = ml.move_id.internal_parent_move_id
                parent_lines = parent_move.move_line_ids.filtered(
                    lambda l: l.lot_id and l.lot_id.exists() and getattr(l, "supply_kind", False) == "parent"
                )
                if parent_lines and parent_lines[0].lot_id:
                    principal_lot = parent_lines[0].lot_id
                    if hasattr(principal_lot, "lot_supply_line_ids") and principal_lot.lot_supply_line_ids:
                        supply = principal_lot.lot_supply_line_ids.filtered(
                            lambda sl: sl.product_id.id == ml.product_id.id and sl.related_lot_id and sl.related_lot_id.exists()
                        )
                        if supply:
                            related_lot = supply[0].related_lot_id
            if not related_lot and principal_lots:
                for principal_lot in principal_lots:
                    if not hasattr(principal_lot, "lot_supply_line_ids") or not principal_lot.lot_supply_line_ids:
                        continue
                    supply = principal_lot.lot_supply_line_ids.filtered(
                        lambda sl: sl.product_id.id == ml.product_id.id and sl.related_lot_id and sl.related_lot_id.exists()
                    )
                    if supply:
                        related_lot = supply[0].related_lot_id
                        break
            if related_lot:
                # Evitar "Este número de serie ya había sido asignado": si ya existe otra línea
                # en el picking con el mismo (product_id, lot_id), fusionar en ella en vez de escribir lot_id.
                existing = picking_lines.filtered(
                    lambda l: l.id != ml.id and l.product_id.id == ml.product_id.id and l.lot_id and l.lot_id.id == related_lot.id
                )
                if existing:
                    target = existing[0]
                    prod_name = ml.product_id.display_name
                    ser_name = related_lot.name
                    if ml.product_id.tracking == "serial":
                        target.quantity = 1.0
                        target.qty_done = max((target.qty_done or 0), (ml.qty_done or 0)) or 1.0
                    else:
                        target.quantity = (target.quantity or 0) + (ml.quantity or 0)
                        target.qty_done = (target.qty_done or 0) + (ml.qty_done or 0)
                    move_id = ml.move_id.id if ml.move_id else None
                    ml.unlink()
                    if move_id:
                        move = self.env["stock.move"].browse(move_id)
                        if move.exists():
                            total = sum(move.move_line_ids.mapped("quantity"))
                            if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                                move.product_uom_qty = total
                    _logger.debug(
                        "Fusionada línea duplicada (producto %s, serie %s) en picking %s",
                        prod_name, ser_name, picking.name
                    )
                else:
                    ml.lot_id = related_lot.id
                    _logger.debug(
                        "Asignado lot_id %s a línea componente en picking %s (producto %s)",
                        related_lot.name, picking.name, ml.product_id.display_name
                    )
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        for ml in picking_lines:
            if ml.lot_id or not ml.lot_name or not ml.product_id or ml.product_id.tracking == "none":
                continue
            lot = self.env["stock.lot"].search([
                ("product_id", "=", ml.product_id.id),
                ("name", "=", ml.lot_name),
                ("company_id", "in", (picking.company_id.id, False)),
            ], limit=1)
            if lot:
                existing = picking_lines.filtered(
                    lambda l: l.id != ml.id and l.product_id.id == ml.product_id.id and l.lot_id and l.lot_id.id == lot.id
                )
                if existing:
                    target = existing[0]
                    if ml.product_id.tracking == "serial":
                        target.quantity = 1.0
                        target.qty_done = max((target.qty_done or 0), (ml.qty_done or 0)) or 1.0
                    else:
                        target.quantity = (target.quantity or 0) + (ml.quantity or 0)
                        target.qty_done = (target.qty_done or 0) + (ml.qty_done or 0)
                    move_id = ml.move_id.id if ml.move_id else None
                    ml.unlink()
                    if move_id:
                        move = self.env["stock.move"].browse(move_id)
                        if move.exists():
                            total = sum(move.move_line_ids.mapped("quantity"))
                            if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                                move.product_uom_qty = total
                else:
                    ml.lot_id = lot.id

    @api.model
    def _consolidate_duplicate_move_lines_for_picking(self, picking):
        """
        Consolida líneas duplicadas (mismo product_id + lot_id) en un picking
        antes de validar. Evita el error "Este número de serie ya había sido asignado".
        Incluye principales Y elementos asociados (p. ej. TPA-P001M / 9CP13030K1 en devoluciones).
        Se llama desde stock.picking.button_validate() y desde _action_done().
        Orden: 1) Consolidar por (product_id, lot_name) sin lot_id. 2) Asignar lot_id a componentes.
        3) Consolidar por (product_id, lot_id). Así no se dispara "ya asignado" al escribir lot_id.
        Retorna el número total de líneas eliminadas (para iterar hasta 0).
        """
        if not picking or not picking.exists() or not picking.move_line_ids:
            return 0
        total_removed = 0
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        # 1) Consolidar por (product_id, lot_name) cuando no hay lot_id (evita duplicados por nombre)
        lines_with_name = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_name and not ml.lot_id)
        if lines_with_name:
            seen_name = {}
            to_remove_name = []
            for ml in lines_with_name:
                key = (ml.product_id.id, (ml.lot_name or "").strip())
                if not key[1]:
                    continue
                if key in seen_name:
                    existing_line = seen_name[key]
                    if ml.product_id.tracking == "serial":
                        existing_line.quantity = 1.0
                        existing_line.qty_done = max((existing_line.qty_done or 0), (ml.qty_done or 0)) or 1.0
                    else:
                        existing_line.quantity = (existing_line.quantity or 0) + (ml.quantity or 0)
                        existing_line.qty_done = (existing_line.qty_done or 0) + (ml.qty_done or 0)
                    to_remove_name.append(ml)
                else:
                    seen_name[key] = ml
            if to_remove_name:
                total_removed += len(to_remove_name)
                moves_to_update = {ml.move_id.id for ml in to_remove_name if ml.move_id and ml.move_id.exists()}
                to_remove_name.unlink()
                for move_id in moves_to_update:
                    move = self.env["stock.move"].browse(move_id)
                    if move.exists():
                        total = sum(move.move_line_ids.mapped("quantity"))
                        if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                            move.product_uom_qty = total
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        # Fusionar líneas que tienen (product_id, lot_name) sin lot_id con la que ya tiene (product_id, lot_id) donde lot_id.name == lot_name
        lines_name_only = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_name and not ml.lot_id)
        lines_with_lot = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_id)
        for ml in lines_name_only:
            name_key = (ml.lot_name or "").strip()
            if not name_key:
                continue
            match = lines_with_lot.filtered(
                lambda l: l.product_id.id == ml.product_id.id and l.lot_id and (l.lot_id.name or "").strip() == name_key
            )
            if match:
                existing = match[0]
                if ml.product_id.tracking == "serial":
                    existing.quantity = 1.0
                    existing.qty_done = max((existing.qty_done or 0), (ml.qty_done or 0)) or 1.0
                else:
                    existing.quantity = (existing.quantity or 0) + (ml.quantity or 0)
                    existing.qty_done = (existing.qty_done or 0) + (ml.qty_done or 0)
                total_removed += 1
                move_id = ml.move_id.id if ml.move_id else None
                ml.unlink()
                if move_id:
                    move = self.env["stock.move"].browse(move_id)
                    if move.exists():
                        total = sum(move.move_line_ids.mapped("quantity"))
                        if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                            move.product_uom_qty = total
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        self._ensure_component_lot_ids_for_picking(picking)
        picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
        # Todas las líneas con product_id y lot_id (principales + asociados)
        lines_with_lot = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_id)
        if not lines_with_lot:
            return total_removed
        seen_combinations = {}
        lines_to_remove = []
        for ml in lines_with_lot:
            key = (ml.product_id.id, ml.lot_id.id)
            if key in seen_combinations:
                existing_line = seen_combinations[key]
                # Serial: no sumar cantidades (1+1=2 invalida); dejar 1 y solo eliminar duplicado
                if ml.product_id.tracking == "serial":
                    existing_line.quantity = 1.0
                    existing_line.qty_done = max((existing_line.qty_done or 0), (ml.qty_done or 0)) or 1.0
                else:
                    existing_line.quantity = (existing_line.quantity or 0) + (ml.quantity or 0)
                    existing_line.qty_done = (existing_line.qty_done or 0) + (ml.qty_done or 0)
                lines_to_remove.append(ml)
            else:
                seen_combinations[key] = ml
        if lines_to_remove:
            total_removed += len(lines_to_remove)
            _logger.info(
                "Consolidando %d líneas duplicadas en picking %s (button_validate)",
                len(lines_to_remove), picking.name or picking.id
            )
            moves_to_update = {ml.move_id.id for ml in lines_to_remove if ml.move_id}
            self.env["stock.move.line"].browse([m.id for m in lines_to_remove]).unlink()
            for move_id in moves_to_update:
                move = self.env["stock.move"].browse(move_id)
                if move.exists():
                    total = sum(move.move_line_ids.mapped("quantity"))
                    if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                        move.product_uom_qty = total
        return total_removed

    @api.model
    def _get_duplicate_serial_report(self, picking):
        """
        Para depuración: devuelve lista de (producto, serie, cantidad de líneas) donde
        el mismo (product_id, lot_id) aparece más de una vez en el picking.
        """
        if not picking or not picking.exists() or not picking.move_line_ids:
            return []
        lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists() and ml.product_id and ml.lot_id)
        from collections import Counter
        key_counts = Counter((ml.product_id.id, ml.lot_id.id) for ml in lines)
        duplicates = [(k[0], k[1], c) for k, c in key_counts.items() if c > 1]
        result = []
        for product_id, lot_id, count in duplicates:
            product = self.env["product.product"].browse(product_id)
            lot = self.env["stock.lot"].browse(lot_id)
            result.append((product.display_name if product.exists() else str(product_id),
                           lot.name if lot.exists() else str(lot_id), count))
        return result

    def _action_done(self):
        """
        Sobrescribe _action_done para consolidar líneas duplicadas de elementos asociados
        antes de procesar, evitando errores de seriales duplicados.
        Los elementos asociados se moverán automáticamente después a través de _move_associated_lots_with_principal.
        """
        # Pre-llenar nombres de lotes para elementos asociados (si aplica)
        self._prefill_lot_name_non_principals_simple()
        
        # IDs de líneas que eliminamos para NO pasarlas a super() (evitar procesar registros borrados)
        ids_removed = set()
        
        # CORRECCIÓN CRÍTICA: Consolidar por PICKING COMPLETO (todas las move_line_ids del picking),
        # no solo las de self, para cubrir duplicados entre distintos moves (mismo product_id+lot_id).
        for picking in self.mapped("picking_id"):
            if not picking or not picking.exists():
                continue
            picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
            lines_with_name = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_name and not ml.lot_id)
            if lines_with_name:
                seen_name = {}
                to_remove_name = []
                for ml in lines_with_name:
                    key = (ml.product_id.id, (ml.lot_name or "").strip())
                    if not key[1]:
                        continue
                    if key in seen_name:
                        existing_line = seen_name[key]
                        if ml.product_id.tracking == "serial":
                            existing_line.quantity = 1.0
                            existing_line.qty_done = max((existing_line.qty_done or 0), (ml.qty_done or 0)) or 1.0
                        else:
                            existing_line.quantity = (existing_line.quantity or 0) + (ml.quantity or 0)
                            existing_line.qty_done = (existing_line.qty_done or 0) + (ml.qty_done or 0)
                        to_remove_name.append(ml)
                    else:
                        seen_name[key] = ml
                if to_remove_name:
                    ids_removed.update(to_remove_name.ids)
                    moves_to_update = {ml.move_id.id for ml in to_remove_name if ml.move_id}
                    to_remove_name.unlink()
                    for move_id in moves_to_update:
                        move = self.env["stock.move"].browse(move_id)
                        if move.exists():
                            total = sum(move.move_line_ids.mapped("quantity"))
                            if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                                move.product_uom_qty = total
            picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
            lines_name_only = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_name and not ml.lot_id)
            lines_with_lot = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_id)
            for ml in lines_name_only:
                name_key = (ml.lot_name or "").strip()
                if not name_key:
                    continue
                match = lines_with_lot.filtered(
                    lambda l: l.product_id.id == ml.product_id.id and l.lot_id and (l.lot_id.name or "").strip() == name_key
                )
                if match:
                    existing = match[0]
                    if ml.product_id.tracking == "serial":
                        existing.quantity = 1.0
                        existing.qty_done = max((existing.qty_done or 0), (ml.qty_done or 0)) or 1.0
                    else:
                        existing.quantity = (existing.quantity or 0) + (ml.quantity or 0)
                        existing.qty_done = (existing.qty_done or 0) + (ml.qty_done or 0)
                    ids_removed.add(ml.id)
                    move_id = ml.move_id.id if ml.move_id else None
                    ml.unlink()
                    if move_id:
                        move = self.env["stock.move"].browse(move_id)
                        if move.exists():
                            total = sum(move.move_line_ids.mapped("quantity"))
                            if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                                move.product_uom_qty = total
            self._ensure_component_lot_ids_for_picking(picking)
            picking_lines = picking.move_line_ids.filtered(lambda ml: ml.id and ml.exists())
            lines_with_lot = picking_lines.filtered(lambda ml: ml.product_id and ml.lot_id)
            # Consolidar duplicados (mismo product_id + lot_id): principales Y asociados
            # Evita "Este número de serie ya había sido asignado" (p. ej. TPA-P001M / 9CP13030K1)
            if lines_with_lot:
                seen_combinations = {}
                lines_to_remove = []
                for ml in lines_with_lot:
                    key = (ml.product_id.id, ml.lot_id.id)
                    if key in seen_combinations:
                        existing_line = seen_combinations[key]
                        if ml.product_id.tracking == "serial":
                            existing_line.quantity = 1.0
                            existing_line.qty_done = max((existing_line.qty_done or 0), (ml.qty_done or 0)) or 1.0
                        else:
                            existing_line.quantity = (existing_line.quantity or 0) + (ml.quantity or 0)
                            existing_line.qty_done = (existing_line.qty_done or 0) + (ml.qty_done or 0)
                        lines_to_remove.append(ml)
                    else:
                        seen_combinations[key] = ml
                if lines_to_remove:
                    _logger.info("Consolidando %d líneas duplicadas en picking %s",
                                 len(lines_to_remove), picking.name or picking.id)
                    ids_removed.update(m.id for m in lines_to_remove)
                    moves_to_update = {ml.move_id.id for ml in lines_to_remove if ml.move_id}
                    self.env["stock.move.line"].browse([m.id for m in lines_to_remove]).unlink()
                    for move_id in moves_to_update:
                        move = self.env["stock.move"].browse(move_id)
                        if move.exists():
                            total = sum(move.move_line_ids.mapped("quantity"))
                            if float_compare(total, move.product_uom_qty, precision_digits=2) != 0:
                                move.product_uom_qty = total
        
        # Llamar al padre con solo las líneas que siguen existiendo (remaining como receptor)
        remaining = self.filtered(lambda ml: ml.id not in ids_removed)
        if remaining:
            res = super(StockMoveLine, remaining)._action_done()
        else:
            res = True
        
        # Vincular seriales a productos principales (solo para recepciones)
        # Usar self completo para vincular correctamente
        self._supplies_link_serials_to_principal()
        
        # Forzar flush para asegurar que los quants se actualicen antes de mover elementos asociados
        self.env.flush_all()
        
        # Mover elementos asociados automáticamente después de procesar los principales
        # Usar self completo para mover todos los elementos asociados
        self._move_associated_lots_with_principal()

        return res


    def _prefill_lot_name_non_principals_simple(self):
        Seq = self.env["ir.sequence"]

        for ml in self:
            # CORRECCIÓN: Validar que move_id y picking_type_id existen antes de acceder
            if not ml.move_id or not ml.move_id.exists():
                continue
            picking_type = ml.move_id.picking_type_id
            if not picking_type or not picking_type.exists() or picking_type.code != "incoming":
                continue
            if getattr(ml, "supply_kind", False) == "parent":
                continue
            if ml.product_id.tracking == "none":
                continue
            if ml.lot_id or ml.lot_name:
                continue
            if not picking_type.use_create_lots and not picking_type.use_existing_lots:
                continue

            nxt = Seq.next_by_code("stock.lot.serial")
            if not nxt:
                # CORRECCIÓN: Validar que purchase_line_id y order_id existen antes de acceder
                po = "PO"
                if ml.move_id.purchase_line_id and ml.move_id.purchase_line_id.exists():
                    if ml.move_id.purchase_line_id.order_id and ml.move_id.purchase_line_id.order_id.exists():
                        po = ml.move_id.purchase_line_id.order_id.name or "PO"
                pick = "PICK"
                if ml.picking_id and ml.picking_id.exists():
                    pick = ml.picking_id.name or "PICK"
                product_code = ml.product_id.default_code if ml.product_id and ml.product_id.exists() else (ml.product_id.id if ml.product_id else "")
                base = f"TMP-{po}-{pick}-{product_code}"
            else:
                base = nxt

            if ml.product_id.tracking == "lot":
                ml.lot_name = base

            elif ml.product_id.tracking == "serial":
                precision = ml.product_uom_id.rounding or 0.0001
                if float_compare(ml.quantity, 1.0, precision_rounding=precision) == 0:
                    ml.lot_name = base
                else:
                    raise UserError(_(
                        "El producto '%(prod)s' se rastrea por SERIE y la línea tiene cantidad %(qty)s. "
                        "Sin crear líneas nuevas no puedo asignar múltiples series. "
                        "Divide la línea a unidades (1) o permite la creación automática de líneas.",
                    ) % {"prod": ml.product_id.display_name, "qty": ml.quantity})

    @api.constrains("lot_id", "qty_done", "product_id")
    def _supplies_enforce_lot_only_for_parent(self):
        for line in self:
            if not line.qty_done:
                continue
            # CORRECCIÓN: Validar que move_id, picking_id y picking_type_id existen antes de acceder
            if not line.move_id or not line.move_id.exists():
                continue
            picking = line.move_id.picking_id
            if not picking or not picking.exists() or not picking.picking_type_id or not picking.picking_type_id.exists() or picking.picking_type_id.code != "incoming":
                continue

            # CORRECCIÓN: Validar que product_id existe antes de acceder
            if not line.product_id or not line.product_id.exists():
                continue
            product = line.product_id

            requires_lot = (
                product.tracking != "none"
                and product.categ_id
                and product.categ_id.property_valuation == "real_time"
            )

            if not requires_lot:
                continue

            if line.supply_kind == "parent" and not line.lot_id:
                raise ValidationError(
                    _("El número de lote o serie es obligatorio para el producto principal.")
                )
            
    def _supplies_link_serials_to_principal(self):
        for picking in self.mapped("picking_id"):
            # CORRECCIÓN: Validar que picking y picking_type_id existen antes de acceder
            if not picking or not picking.exists() or not picking.picking_type_id or not picking.picking_type_id.exists() or picking.picking_type_id.code != "incoming":
                continue

            lines = picking.move_line_ids

            # CORRECCIÓN: Validar que lot_id existe antes de filtrar
            principal_lines = lines.filtered(lambda l: l.supply_kind == "parent" and l.lot_id and l.lot_id.exists())
            principal_product = principal_lines[:1].product_id if principal_lines and len(principal_lines) > 0 and principal_lines[0].product_id and principal_lines[0].product_id.exists() else False
            principal_lots = principal_lines.mapped("lot_id") if principal_lines else self.env['stock.lot']

            if principal_lots:
                vals_pl = {"is_principal": True}
                # CORRECCIÓN: Odoo 19 puede no tener move_ids_without_package; usar move_ids
                ptr = False
                moves = getattr(picking, 'move_ids_without_package', None) or picking.move_ids
                if moves and len(moves) > 0:
                    ptr = moves[0].purchase_tracking_ref or False
                if ptr:
                    vals_pl["purchase_tracking_ref"] = ptr
                if principal_product:
                    vals_pl["principal_product_id"] = principal_product.id
                principal_lots.write(vals_pl)

                for lot in principal_lots:
                    if lot and lot.exists() and hasattr(lot, "lot_supply_line_ids") and not lot.lot_supply_line_ids:
                        lot.action_initialize_supply_lines()

            # CORRECCIÓN: Validar que lot_id existe antes de filtrar
            child_lines = lines.filtered(
                lambda l: l.lot_id and l.lot_id.exists() and l.supply_kind in ("component", "peripheral", "complement")
            )
            if not child_lines:
                continue

            single_principal_lot = principal_lots[0] if len(principal_lots) == 1 and principal_lots[0] and principal_lots[0].exists() else False
            # CORRECCIÓN: Odoo 19 puede no tener move_ids_without_package; usar move_ids
            purchase_ref = False
            moves = getattr(picking, 'move_ids_without_package', None) or picking.move_ids
            if moves and len(moves) > 0:
                purchase_ref = moves[0].purchase_tracking_ref or False

            for ml in child_lines:
                # CORRECCIÓN: Validar que lot_id existe antes de acceder
                if not ml.lot_id or not ml.lot_id.exists():
                    continue
                lot = ml.lot_id
                vals = {}
                if principal_product:
                    vals["principal_product_id"] = principal_product.id
                if single_principal_lot:
                    vals["principal_lot_id"] = single_principal_lot.id
                if purchase_ref:
                    vals["purchase_tracking_ref"] = purchase_ref
                if vals:
                    lot.write(vals)

            if single_principal_lot and single_principal_lot.exists():
                SupplyLine = self.env["stock.lot.supply.line"]
                Quant = self.env["stock.quant"]

                used_related_global = set(SupplyLine.search([
                    ("related_lot_id", "!=", False),
                ]).mapped("related_lot_id").filtered(lambda r: r and r.exists()).ids)

                used_related_same_parent = set(SupplyLine.search([
                    ("lot_id", "=", single_principal_lot.id),
                    ("related_lot_id", "!=", False),
                ]).mapped("related_lot_id").filtered(lambda r: r and r.exists()).ids)

                blocked = used_related_global | used_related_same_parent

                by_product_available = {}
                # CORRECCIÓN: Validar que location_id existe antes de acceder
                principal_loc = single_principal_lot.location_id if single_principal_lot.location_id and single_principal_lot.location_id.exists() else False

                child_lots = self.env["stock.lot"].search([
                    ("principal_lot_id", "=", single_principal_lot.id),
                ])

                for cl in child_lots:
                    if cl.id in blocked:
                        continue
                    # CORRECCIÓN: Validar que product_id existe antes de acceder
                    if not cl.product_id or not cl.product_id.exists():
                        continue
                    if principal_loc:
                        has_stock_here = bool(Quant.search_count([
                            ("lot_id", "=", cl.id),
                            ("location_id", "=", principal_loc.id),
                            ("quantity", ">", 0),
                        ]))
                        if not has_stock_here:
                            continue
                    by_product_available.setdefault(cl.product_id.id, []).append(cl.id)

                # CORRECCIÓN: Validar que lot_supply_line_ids existe antes de filtrar
                pending_lines = single_principal_lot.lot_supply_line_ids.filtered(lambda sl: not sl.related_lot_id or not sl.related_lot_id.exists()) if hasattr(single_principal_lot, 'lot_supply_line_ids') else self.env['stock.lot.supply.line']

                for sl in pending_lines:
                    # CORRECCIÓN: Validar que product_id existe antes de acceder
                    if not sl.product_id or not sl.product_id.exists():
                        continue
                    pool = by_product_available.get(sl.product_id.id, [])
                    if not pool:
                        continue
                    chosen = pool.pop(0)
                    if chosen:
                        sl.related_lot_id = chosen

    def _move_associated_lots_with_principal(self):
        """
        Mueve los lotes asociados (componentes, periféricos, complementos) 
        a la misma ubicación donde está el lote principal, sin importar la ruta.
        Funciona para cualquier ubicación (China, Alistamiento, Salida, etc.)
        """
        Quant = self.env['stock.quant']
        
        # Agrupar por picking para procesar todos los movimientos juntos
        for picking in self.mapped("picking_id"):
            if not picking or not picking.exists():
                continue
            
            # Buscar líneas principales que se han movido
            principal_lines = picking.move_line_ids.filtered(
                lambda ml: ml.supply_kind == 'parent' 
                and ml.lot_id 
                and ml.lot_id.exists()
                and ml.qty_done > 0
            )
            
            if not principal_lines:
                _logger.debug("No se encontraron líneas principales en picking %s", picking.name or picking.id)
                continue
            
            _logger.info("Procesando %d líneas principales en picking %s", len(principal_lines), picking.name or picking.id)
            
            # Procesar cada lote principal
            for principal_line in principal_lines:
                principal_lot = principal_line.lot_id
                
                if not principal_lot or not principal_lot.exists():
                    continue
                
                # Obtener la ubicación ACTUAL del quant del lote principal después del movimiento
                # Esto asegura que usamos la ubicación real donde quedó el principal
                principal_quants = Quant.sudo().search([
                    ('lot_id', '=', principal_lot.id),
                    ('quantity', '>', 0),
                ], order='id desc')
                
                if not principal_quants:
                    _logger.warning("No se encontraron quants para lote principal %s", principal_lot.name or principal_lot.id)
                    continue
                
                # Obtener la ubicación donde está el principal (puede haber múltiples quants en la misma ubicación)
                # Agrupar por ubicación y tomar la ubicación con mayor cantidad
                location_quantities = {}
                for pq in principal_quants:
                    loc_id = pq.location_id.id
                    if loc_id not in location_quantities:
                        location_quantities[loc_id] = 0
                    location_quantities[loc_id] += pq.quantity
                
                # Obtener la ubicación con mayor cantidad (la ubicación principal)
                if not location_quantities:
                    _logger.warning("No se pudo determinar la ubicación del lote principal %s", principal_lot.name or principal_lot.id)
                    continue
                
                principal_location_id = max(location_quantities.items(), key=lambda x: x[1])[0]
                destination_location = self.env['stock.location'].browse(principal_location_id)
                
                if not destination_location or not destination_location.exists():
                    _logger.warning("Ubicación destino inválida para lote principal %s", principal_lot.name or principal_lot.id)
                    continue
                
                _logger.info("Lote principal %s está en ubicación: %s (cantidad: %s)", 
                            principal_lot.name or principal_lot.id, 
                            destination_location.name or destination_location.id,
                            location_quantities[principal_location_id])
                
                # Verificar si el lote principal tiene elementos asociados
                if not hasattr(principal_lot, 'lot_supply_line_ids'):
                    _logger.debug("Lote %s no tiene atributo lot_supply_line_ids", principal_lot.name or principal_lot.id)
                    continue
                
                if not principal_lot.lot_supply_line_ids:
                    _logger.debug("Lote %s no tiene elementos asociados", principal_lot.name or principal_lot.id)
                    continue
                
                # Obtener todos los lotes asociados
                associated_lots = principal_lot.lot_supply_line_ids.filtered(
                    lambda sl: sl.related_lot_id and sl.related_lot_id.exists()
                ).mapped('related_lot_id')
                
                if not associated_lots:
                    _logger.debug("Lote %s no tiene lotes asociados válidos", principal_lot.name or principal_lot.id)
                    continue
                
                _logger.info("Encontrados %d lotes asociados para lote principal %s", len(associated_lots), principal_lot.name or principal_lot.id)
                
                # Mover cada lote asociado a la misma ubicación donde está el principal
                # Esto funciona para cualquier ubicación (China, Alistamiento, Salida, etc.)
                for associated_lot in associated_lots:
                    if not associated_lot or not associated_lot.exists():
                        continue
                    
                    _logger.info("Verificando lote asociado %s - debe estar en: %s", 
                               associated_lot.name or associated_lot.id, 
                               destination_location.name or destination_location.id)
                    
                    # Buscar TODOS los quants del lote asociado (en cualquier ubicación)
                    all_associated_quants = Quant.sudo().search([
                        ('lot_id', '=', associated_lot.id),
                        ('quantity', '>', 0),
                    ])
                    
                    if not all_associated_quants:
                        _logger.warning("No se encontraron quants para lote asociado %s", associated_lot.name or associated_lot.id)
                        continue
                    
                    # Separar quants que están en la ubicación correcta vs los que no
                    correct_location_quants = all_associated_quants.filtered(
                        lambda q: q.location_id.id == destination_location.id
                    )
                    wrong_location_quants = all_associated_quants.filtered(
                        lambda q: q.location_id.id != destination_location.id
                    )
                    
                    if not wrong_location_quants:
                        # Todos los quants ya están en la ubicación correcta
                        _logger.debug("Lote asociado %s ya está en la ubicación correcta %s", 
                                    associated_lot.name or associated_lot.id,
                                    destination_location.name or destination_location.id)
                        continue
                    
                    # Calcular la cantidad total a mover
                    total_quantity_to_move = sum(wrong_location_quants.mapped('quantity'))
                    _logger.info("Moviendo lote asociado %s: %s unidades desde %d ubicación(es) incorrecta(s) hacia %s", 
                               associated_lot.name or associated_lot.id,
                               total_quantity_to_move,
                               len(wrong_location_quants),
                               destination_location.name or destination_location.id)
                    
                    
                    # Mover cada quant del lote asociado desde ubicaciones incorrectas hacia la ubicación del principal
                    for quant in wrong_location_quants:
                        if not quant or not quant.exists():
                            continue
                        
                        source_location = quant.location_id
                        quantity_to_move = quant.quantity
                        product = quant.product_id
                        company = quant.company_id
                        
                        if not source_location or not source_location.exists():
                            continue
                        
                        if not product or not product.exists():
                            continue
                        
                        _logger.info("Moviendo quant: lote=%s, producto=%s, cantidad=%s, desde=%s, hacia=%s", 
                                   associated_lot.name or associated_lot.id,
                                   product.name or product.id,
                                   quantity_to_move,
                                   source_location.name or source_location.id,
                                   destination_location.name or destination_location.id)
                        
                        try:
                            # Usar _update_available_quantity para mover el quant correctamente
                            # Primero reducir en origen
                            Quant.sudo()._update_available_quantity(
                                product.id,
                                source_location.id,
                                -quantity_to_move,
                                lot_id=associated_lot.id,
                                package_id=False,
                                owner_id=False,
                                in_date=False,
                            )
                            
                            # Luego aumentar en destino
                            Quant.sudo()._update_available_quantity(
                                product.id,
                                destination_location.id,
                                quantity_to_move,
                                lot_id=associated_lot.id,
                                package_id=False,
                                owner_id=False,
                                in_date=False,
                            )
                            
                            _logger.info("✓ Quant movido exitosamente")
                            
                        except Exception as e:
                            _logger.error("Error al mover quant del lote asociado %s: %s", associated_lot.name or associated_lot.id, str(e))
                            # Intentar método alternativo si falla
                            try:
                                # Buscar o crear quant en la ubicación destino
                                dest_quant = Quant.sudo().search([
                                    ('lot_id', '=', associated_lot.id),
                                    ('location_id', '=', destination_location.id),
                                    ('product_id', '=', product.id),
                                ], limit=1)
                                
                                if dest_quant:
                                    # Actualizar cantidad en destino
                                    dest_quant.quantity += quantity_to_move
                                else:
                                    # Crear nuevo quant en destino
                                    Quant.sudo().create({
                                        'lot_id': associated_lot.id,
                                        'location_id': destination_location.id,
                                        'product_id': product.id,
                                        'quantity': quantity_to_move,
                                        'company_id': company.id if company else False,
                                    })
                                
                                # Reducir o eliminar quant en origen
                                if quant.quantity <= quantity_to_move:
                                    quant.unlink()
                                else:
                                    quant.quantity -= quantity_to_move
                                
                                _logger.info("✓ Quant movido usando método alternativo")
                            except Exception as e2:
                                _logger.error("Error en método alternativo: %s", str(e2))
