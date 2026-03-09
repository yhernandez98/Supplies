# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


def _run_consolidation_loop(picking, max_iter=10):
    """Ejecuta consolidación en bucle hasta que no se elimine ninguna línea. Retorna total eliminado."""
    total = 0
    for _ in range(max_iter):
        removed = picking.env["stock.move.line"]._consolidate_duplicate_move_lines_for_picking(picking)
        total += removed
        if removed == 0:
            break
    return total

class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Campo computed para mostrar solo líneas principales
    move_ids_main_only = fields.One2many(
        'stock.move',
        'picking_id',
        string='Movimientos principales',
        compute='_compute_move_ids_main_only',
        store=False,
        help='Solo muestra movimientos con supply_kind = parent'
    )
    
    @api.depends('move_ids_without_package', 'move_ids_without_package.supply_kind')
    def _compute_move_ids_main_only(self):
        """Calcular movimientos principales (solo supply_kind = 'parent')"""
        for picking in self:
            try:
                picking.move_ids_main_only = picking.move_ids_without_package.filtered(
                    lambda m: hasattr(m, 'supply_kind') and m.supply_kind == 'parent'
                )
            except Exception:
                picking.move_ids_main_only = self.env['stock.move']
    
    # Campo computed para mostrar solo move_line_ids principales en "Operaciones detalladas"
    move_line_ids_main_only = fields.One2many(
        'stock.move.line',
        'picking_id',
        string='Líneas principales',
        compute='_compute_move_line_ids_main_only',
        store=False,
        help='Solo muestra move_line_ids con supply_kind = parent'
    )
    
    @api.depends('move_line_ids_without_package', 'move_line_ids_without_package.supply_kind')
    def _compute_move_line_ids_main_only(self):
        """Calcular move_line_ids principales (solo supply_kind = 'parent')"""
        for picking in self:
            try:
                picking.move_line_ids_main_only = picking.move_line_ids_without_package.filtered(
                    lambda ml: hasattr(ml, 'supply_kind') and ml.supply_kind == 'parent'
                )
            except Exception:
                picking.move_line_ids_main_only = self.env['stock.move.line']
    

    def action_debug_consolidate_serial_lines(self):
        """
        Botón de depuración: ejecuta consolidación en bucle y muestra si quedan
        duplicados (producto + serie repetidos). Ayuda a diagnosticar el error
        "Este número de serie ya había sido asignado".
        """
        self.ensure_one()
        if not self.move_line_ids:
            raise UserError(_("Este traslado no tiene líneas de operación."))
        total_merged = _run_consolidation_loop(self)
        report = self.env["stock.move.line"]._get_duplicate_serial_report(self)
        if report:
            lines_msg = "\n".join(
                _("• Producto: %s | Serie: %s | Líneas repetidas: %s") % (prod, ser, cnt)
                for prod, ser, cnt in report
            )
            raise UserError(
                _("Consolidación ejecutada (%s líneas fusionadas).\n\n"
                  "Aún hay duplicados (mismo producto + mismo número de serie en varias líneas):\n\n%s\n\n"
                  "Estos productos/series provocan el error al validar. Revise por qué hay varias líneas "
                  "con el mismo serial (p. ej. componentes/periféricos repetidos).")
                % (total_merged, lines_msg)
            )
        raise UserError(
            _("Consolidación OK.\n\nSe fusionaron %s líneas duplicadas. No quedan duplicados (producto + serie).\n"
              "Puede intentar validar de nuevo.")
            % total_merged
        )

    def action_detailed_operations(self):
        """
        Sobrescribe el método estándar para filtrar solo productos principales
        en la vista de "Operaciones detalladas".
        """
        action = super().action_detailed_operations()
        if action and isinstance(action, dict):
            # Agregar dominio para mostrar solo productos principales
            domain = action.get('domain', [])
            if not any('supply_kind' in str(d) for d in domain):
                domain = domain + [('supply_kind', '=', 'parent')]
            action['domain'] = domain
        return action

    def button_validate(self):
        # Consolidar líneas duplicadas (mismo product_id+lot_id) ANTES de validar
        # para evitar "Este número de serie ya había sido asignado" (entrega/devolución).
        # Ejecutar en bucle hasta que no queden duplicados (máx 10 pasadas).
        for picking in self:
            if picking.exists() and picking.move_line_ids:
                for _ in range(10):
                    removed = self.env["stock.move.line"]._consolidate_duplicate_move_lines_for_picking(picking)
                    if removed == 0:
                        break
        # Validar el picking
        res = super().button_validate()
        self._log_supplies_purchase_history()
        # Cuando un equipo sale de la ubicación del cliente (devolución), marcar Fecha Finalizacion Renting
        try:
            self._set_renting_exit_date_on_return()
        except Exception as e:
            _logger.warning("Error al actualizar Fecha Finalizacion Renting en devoluciones: %s", str(e))
        # Cuando se ENTREGA de nuevo un equipo al cliente, limpiar fecha de salida para no mostrar la anterior
        try:
            self._clear_renting_dates_on_delivery_to_client()
        except Exception as e:
            _logger.warning("Error al limpiar fechas Renting en entregas al cliente: %s", str(e))
        
        # Después de validar, intentar confirmar pickings destino que estén en borrador
        try:
            for picking in self:
                if not picking or not picking.exists():
                    continue
                
                # Buscar movimientos que tienen move_dest_ids (siguiente etapa en la cadena)
                moves_with_dest = picking.move_ids.filtered(
                    lambda m: m.move_dest_ids and m.state == 'done'
                )
                
                if moves_with_dest:
                    # Para cada movimiento destino, confirmar su picking si está en borrador
                    for move in moves_with_dest:
                        for dest_move in move.move_dest_ids:
                            try:
                                if dest_move.picking_id and dest_move.picking_id.exists():
                                    dest_picking = dest_move.picking_id
                                    if dest_picking.state == 'draft':
                                        _logger.info("Confirmando automáticamente picking %s creado desde move_dest_ids", 
                                                   dest_picking.name or dest_picking.id)
                                        dest_picking.action_confirm()
                            except Exception as e:
                                _logger.warning("Error al confirmar picking destino: %s", str(e))
                                continue
        except Exception as e:
            _logger.warning("Error al procesar confirmación automática de pickings destino: %s", str(e))
        
        return res

    def _is_client_stock_location(self, location):
        """
        True si la ubicación es "stock del cliente": uso customer, o (sub)ubicación de un almacén con partner.
        Incluye la ubicación y cualquier hijo (ej. SOCIE/Existencias).
        """
        if not location or not location.exists():
            return False
        # La propia ubicación tiene uso customer
        if getattr(location, 'usage', None) == 'customer':
            return True
        # Almacén de cliente: warehouse con partner_id cuya lot_stock_id es esta ubicación
        wh = self.env['stock.warehouse'].sudo().search([
            ('lot_stock_id', '=', location.id),
            ('partner_id', '!=', False),
        ], limit=1)
        if wh:
            return True
        # Ubicación hija de una con uso customer (ej. Cliente/Existencias)
        parent = location.location_id
        while parent and parent.exists():
            if getattr(parent, 'usage', None) == 'customer':
                return True
            wh_parent = self.env['stock.warehouse'].sudo().search([
                ('lot_stock_id', '=', parent.id),
                ('partner_id', '!=', False),
            ], limit=1)
            if wh_parent:
                return True
            parent = parent.location_id
        return False

    def _is_return_picking_type(self, picking):
        """True solo si el tipo de operación es de devolución (no entrega, alistamiento, etc.)."""
        if not picking or not picking.exists() or not picking.picking_type_id:
            return False
        name = (picking.picking_type_id.name or '').lower()
        return 'devolución' in name or 'devolucion' in name

    def _set_renting_exit_date_on_return(self):
        """
        Cuando el picking está hecho y algún movimiento SACA producto de una ubicación de cliente,
        actualiza Fecha Finalizacion Renting (exit_date) en los lotes. No depende del nombre del
        tipo de operación (p. ej. aunque no se llame "Devolución"). No toca entregas (destino = cliente).
        """
        today = fields.Date.context_today(self)
        for picking in self:
            if picking.state != 'done' or not picking.exists():
                continue
            for move in picking.move_ids:
                if move.state != 'done':
                    continue
                src = move.location_id
                if not self._is_client_stock_location(src):
                    continue
                for line in move.move_line_ids:
                    if not line.lot_id or not line.lot_id.exists():
                        continue
                    lot = line.lot_id
                    if not hasattr(lot, 'exit_date'):
                        continue
                    lot.sudo().write({'exit_date': today})
                    _logger.info(
                        "Actualizada Fecha Finalizacion Renting (exit_date=%s) en lote %s (salida desde ubicación cliente %s)",
                        today, lot.name, src.complete_name
                    )

    def _clear_renting_dates_on_delivery_to_client(self):
        """
        Cuando el picking es una ENTREGA al cliente (producto entra a ubicación de cliente),
        limpia exit_date y last_exit_date_display en los lotes y establece entry_date a la
        fecha de la entrega, para que "Tiempo En Sitio" y "Días En Sitio" cuenten desde la
        reentrega (mismo equipo entregado de nuevo al cliente).
        """
        today = fields.Date.context_today(self)
        for picking in self:
            if picking.state != 'done' or not picking.exists():
                continue
            if self._is_return_picking_type(picking):
                continue
            # Fecha de la entrega: date_done del picking o hoy
            delivery_date = today
            if picking.date_done:
                delivery_date = (
                    picking.date_done.date()
                    if hasattr(picking.date_done, 'date') else picking.date_done
                )
            for move in picking.move_ids:
                if move.state != 'done':
                    continue
                dest = move.location_dest_id
                if not dest or not self._is_client_stock_location(dest):
                    continue
                for line in move.move_line_ids:
                    if not line.lot_id or not line.lot_id.exists():
                        continue
                    lot = line.lot_id
                    vals = {}
                    if hasattr(lot, 'exit_date') and lot.exit_date:
                        vals['exit_date'] = False
                    if hasattr(lot, 'last_exit_date_display') and lot.last_exit_date_display:
                        vals['last_exit_date_display'] = False
                    # Siempre actualizar entry_date a la fecha de esta entrega para que Tiempo En Sitio cuente desde la reentrega
                    if hasattr(lot, 'entry_date'):
                        vals['entry_date'] = delivery_date
                    if not vals:
                        continue
                    lot.sudo().write(vals)
                    _logger.info(
                        "Entrega al cliente: lote %s - entry_date=%s, fechas salida limpiadas (%s)",
                        lot.name, delivery_date, dest.complete_name
                    )
                    # Refrescar la suscripción para que la vista muestre las nuevas fechas
                    if hasattr(lot, 'active_subscription_id') and lot.active_subscription_id and hasattr(lot.active_subscription_id, 'invalidate_recordset'):
                        lot.active_subscription_id.invalidate_recordset(['grouped_product_ids'])

    @api.model
    def action_backfill_renting_exit_dates(self):
        """
        Actualiza Fecha Finalizacion Renting (exit_date) en lotes de devoluciones ya validadas.
        Busca todos los movimientos hechos que salieron de una ubicación de cliente y asigna
        exit_date = fecha del movimiento a cada lote involucrado (para que la suscripción calcule bien).
        """
        updated = 0
        Move = self.env['stock.move'].sudo()
        done_moves = Move.search([
            ('state', '=', 'done'),
            ('location_id', '!=', False),
        ])
        for move in done_moves:
            if not move.picking_id or not self._is_return_picking_type(move.picking_id):
                continue
            if not self._is_client_stock_location(move.location_id):
                continue
            # Fecha del movimiento (cuando se hizo la devolución)
            move_date = None
            if move.picking_id and move.picking_id.date_done:
                move_date = (move.picking_id.date_done.date()
                             if hasattr(move.picking_id.date_done, 'date') else move.picking_id.date_done)
            elif move.date:
                move_date = (move.date.date() if hasattr(move.date, 'date') else move.date)
            if not move_date:
                continue
            for line in move.move_line_ids:
                if not line.lot_id or not line.lot_id.exists() or not hasattr(line.lot_id, 'exit_date'):
                    continue
                line.lot_id.sudo().write({'exit_date': move_date})
                updated += 1
                _logger.info(
                    "Backfill: exit_date=%s en lote %s (movimiento %s)",
                    move_date, line.lot_id.name, move.picking_id.name if move.picking_id else move.id
                )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fecha Finalizacion Renting actualizada'),
                'message': _('Se actualizó exit_date en %s lote(s) de devoluciones ya validadas.') % updated,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_clear_exit_date_from_deliveries(self):
        """
        Corrige lotes a los que se les puso Fecha Finalizacion Renting por error al validar
        una ENTREGA (Alistamiento, Transporte, etc.). Solo limpia exit_date cuando el último
        movimiento desde ubicación de cliente de ese lote NO fue una devolución.
        """
        Lot = self.env['stock.lot'].sudo()
        lots_with_exit = Lot.search([('exit_date', '!=', False)])
        if not hasattr(Lot, 'exit_date'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin cambios'),
                    'message': _('El modelo de lote no tiene campo exit_date.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        cleared = 0
        for lot in lots_with_exit:
            lines = self.env['stock.move.line'].sudo().search([
                ('lot_id', '=', lot.id),
                ('move_id.state', '=', 'done'),
                ('move_id.location_id', '!=', False),
            ])
            lines_from_client = lines.filtered(lambda l: self._is_client_stock_location(l.move_id.location_id))
            if not lines_from_client:
                continue
            # Ordenar por fecha del movimiento (más reciente primero)
            def _move_done_date(ml):
                p = ml.move_id.picking_id
                d = p.date_done if p and p.date_done else ml.move_id.date
                if d and hasattr(d, 'date'):
                    return d.date()
                return d or fields.Date.from_string('1900-01-01')
            most_recent_line = max(lines_from_client, key=_move_done_date)
            picking = most_recent_line.move_id.picking_id
            if self._is_return_picking_type(picking):
                continue
            lot.sudo().write({'exit_date': False})
            cleared += 1
            _logger.info(
                "Corrección: quitada exit_date del lote %s (último movimiento desde cliente fue entrega: %s)",
                lot.name, picking.picking_type_id.name if picking and picking.picking_type_id else 'N/A'
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Corrección aplicada'),
                'message': _('Se quitó Fecha Finalizacion Renting en %s lote(s) que la tenían por error (entregas).') % cleared,
                'type': 'success',
                'sticky': False,
            },
        }

    def _log_supplies_purchase_history(self):
        """Registra el historial de compras de componentes/periféricos/complementos."""
        try:
            History = self.env["supplies.item.history"]

            # CORRECCIÓN: Validar que picking_type_id existe antes de acceder a code
            for picking in self.filtered(lambda p: p.picking_type_id and p.picking_type_id.exists() and p.picking_type_id.code == "incoming"):
                try:
                    default_date = picking.date_done or fields.Datetime.now()
                    partner = picking.partner_id

                    for move in picking.move_ids_without_package:
                        try:
                            kind = move.supply_kind
                            if kind not in ("component", "peripheral", "complement"):
                                continue

                            # CORRECCIÓN: Validar que purchase_line_id existe antes de acceder
                            parent_prod = False
                            if move.supply_parent_product_id and move.supply_parent_product_id.exists():
                                parent_prod = move.supply_parent_product_id
                            elif move.purchase_line_id and move.purchase_line_id.exists() and move.purchase_line_id.product_id:
                                parent_prod = move.purchase_line_id.product_id
                            parent_tmpl = parent_prod.product_tmpl_id if parent_prod and parent_prod.exists() else False

                            # CORRECCIÓN: Validar que purchase_line_id y order_id existen antes de acceder
                            po = False
                            if move.purchase_line_id and move.purchase_line_id.exists():
                                if move.purchase_line_id.order_id and move.purchase_line_id.order_id.exists():
                                    po = move.purchase_line_id.order_id
                            po_date = getattr(po, "date_order", False) if po else default_date
                            vendor = getattr(po, "partner_id", False) if po else partner

                            qty = move.quantity or move.product_uom_qty
                            uom = move.product_uom
                            if parent_tmpl:
                                vals = {
                                    "parent_product_tmpl_id": parent_tmpl.id if parent_tmpl else False,
                                    "item_type": kind, 
                                    "product_id": move.product_id.id,
                                    "quantity": qty,
                                    "uom_id": uom.id if uom else False,
                                    "purchase_id": po.id if po else False,
                                    "purchase_date": po_date,
                                    "vendor_id": vendor.id if vendor else False,
                                    "state": picking.state, 
                                }
                                History.create(vals)
                        except Exception as e:
                            _logger.warning("Error al registrar historial para move %s: %s", move.id if move else 'N/A', str(e))
                            continue
                except Exception as e:
                    _logger.warning("Error al procesar historial para picking %s: %s", picking.id if picking else 'N/A', str(e))
                    continue
        except Exception as e:
            _logger.warning("Error al inicializar historial de compras: %s", str(e))


    def action_assign_supplies_relations(self):
        self.ensure_one()

        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]

        # CORRECCIÓN: Filtrar movimientos padres y asegurar que cada uno se procese independientemente
        parent_moves = self.move_ids_without_package.filtered(
            lambda m: m.state in ("draft", "confirmed", "waiting", "assigned") and 
                     m.supply_kind == "parent" and
                     m.product_id and m.product_id.exists()
        )
        if not parent_moves:
            raise UserError(_("No hay líneas 'padre' para explotar en este traslado."))
        
        # CORRECCIÓN: Ordenar los movimientos padres por ID para procesarlos de forma consistente
        parent_moves = parent_moves.sorted(lambda m: m.id)

        def _explode_of(parent_move, skip_complements=False):
            """Devuelve [(kind, product, qty, uom)] según el template del padre multiplicado por la qty.
            
            Args:
                parent_move: Movimiento padre
                skip_complements: Si es True, no incluye complementos en la explosión
            """
            # CORRECCIÓN: Validar que product_id y product_tmpl_id existen
            if not parent_move.product_id or not parent_move.product_id.exists():
                return []
            tmpl = parent_move.product_id.product_tmpl_id
            if not tmpl or not tmpl.exists():
                return []
            qty_parent = parent_move.product_uom_qty or 0.0
            # CORRECCIÓN: Validar que uom_id existe antes de acceder
            uom_parent = parent_move.product_uom if parent_move.product_uom and parent_move.product_uom.exists() else (
                parent_move.product_id.uom_id if parent_move.product_id.uom_id and parent_move.product_id.uom_id.exists() else False
            )
            if not uom_parent:
                return []

            out = []

            def _collect(lines, kind):
                for item in (lines or []):
                    pr = item["product"]
                    uom = item["uom"]
                    qty = (item.get("qty") or 0.0) * qty_parent
                    if uom != pr.uom_id:
                        qty = uom._compute_quantity(qty, pr.uom_id, rounding_method="HALF-UP")
                    out.append((kind, pr, qty, pr.uom_id))

            if getattr(tmpl, "is_composite", False):
                _collect(tmpl._explode_components(1.0, uom_parent), "component")
            if getattr(tmpl, "use_peripherals", False):
                _collect(tmpl._explode_peripherals(1.0, uom_parent), "peripheral")
            # Para complementos: solo crear si no se deben omitir
            # Esto evita duplicar complementos que ya fueron recibidos
            if getattr(tmpl, "use_complements", False) and not skip_complements:
                _collect(tmpl._explode_complements(1.0, uom_parent), "complement")

            return out

        def _get_principal_lot_from_move(parent_move):
            """Obtiene el lote principal del movimiento padre desde las move_line_ids.
            
            SIGUE LA LÓGICA DEL MÓDULO PRODUCTIVO: Devuelve un solo lote (el primero).
            Cada movimiento padre se procesa independientemente, por lo que cada uno
            obtiene su propio lote principal y crea sus propios movimientos hijos.
            """
            # CORRECCIÓN: Validar que move_line_ids existe antes de filtrar
            if not parent_move.move_line_ids:
                return False
            
            # Buscar en las move_line_ids del movimiento padre
            # CORRECCIÓN: Filtrar solo las move_lines que pertenecen a ESTE movimiento padre específico
            parent_move_lines = parent_move.move_line_ids.filtered(
                lambda ml: ml.move_id and ml.move_id.id == parent_move.id and
                          ml.lot_id and ml.lot_id.exists()
            )
            
            if parent_move_lines:
                principal_lot = parent_move_lines[0].lot_id
                # Verificar que el lote sea principal y tenga líneas de suministro con lotes asignados
                if principal_lot and principal_lot.exists() and hasattr(principal_lot, 'lot_supply_line_ids'):
                    supply_lines_with_lots = principal_lot.lot_supply_line_ids.filtered(
                        lambda sl: sl.related_lot_id and sl.related_lot_id.exists()
                    )
                    if supply_lines_with_lots:
                        return principal_lot
            return False

        for parent in parent_moves:
            # CORRECCIÓN: Validar que el parent tiene product_id antes de continuar
            if not parent.product_id or not parent.product_id.exists():
                continue
            
            # Verificar si ya existen movimientos de complementos antes de eliminar
            # Esto evita eliminar y recrear complementos que ya fueron recibidos
            existing_complement_moves = self.move_ids_without_package.filtered(
                lambda m: m.supply_kind == "complement" and 
                         m.internal_parent_move_id and m.internal_parent_move_id.id == parent.id
            )
            
            # CORRECCIÓN CRÍTICA: Eliminar movimientos hijos SOLO si pertenecen a ESTE padre específico
            # Esto asegura que cuando hay múltiples productos principales, cada uno mantenga sus propios hijos
            # IMPORTANTE: No eliminar hijos de otros padres en el mismo picking
            children = parent.internal_child_move_ids.filtered(
                lambda m: m.state in ("draft", "confirmed", "waiting", "assigned") and
                         m.internal_parent_move_id and m.internal_parent_move_id.id == parent.id and
                         m.picking_id and m.picking_id.id == self.id
            )
            if children:
                # Si hay complementos existentes, solo eliminar componentes y periféricos
                if existing_complement_moves:
                    children_to_delete = children.filtered(
                        lambda m: m.supply_kind != "complement"
                    )
                    if children_to_delete:
                        children_to_delete.unlink()
                else:
                    # Si no hay complementos existentes, eliminar todos los hijos de ESTE padre
                    children.unlink()

            # SIGUE LA LÓGICA DEL MÓDULO PRODUCTIVO: Obtener el lote principal del movimiento padre
            # Cada movimiento padre se procesa independientemente, por lo que cada uno
            # obtiene su propio lote principal y crea sus propios movimientos hijos
            principal_lot = _get_principal_lot_from_move(parent)
            
            # Si hay lote principal con productos relacionados, usar esos lotes específicos
            if principal_lot and principal_lot.exists() and hasattr(principal_lot, 'lot_supply_line_ids'):
                supply_lines = principal_lot.lot_supply_line_ids.filtered(
                    lambda sl: sl.related_lot_id and sl.related_lot_id.exists()
                )
                
                if supply_lines:
                    # Usar los lotes relacionados que ya están asignados en la recepción
                    qty_parent = parent.product_uom_qty or 0.0
                    
                    for supply_line in supply_lines:
                        related_lot = supply_line.related_lot_id
                        if not related_lot or not related_lot.exists():
                            continue
                        
                        # CORRECCIÓN: Validar que product_id existe antes de acceder
                        if not related_lot.product_id or not related_lot.product_id.exists():
                            continue
                        related_product = related_lot.product_id
                        item_type = supply_line.item_type  # 'component', 'peripheral', 'complement'
                        
                        # Omitir complementos si ya existen
                        if item_type == 'complement' and existing_complement_moves:
                            continue
                        
                        # Mapear item_type a supply_kind
                        supply_kind_map = {
                            'component': 'component',
                            'peripheral': 'peripheral',
                            'complement': 'complement',
                            'monitor': 'monitor',
                            'ups': 'ups',
                        }
                        supply_kind = supply_kind_map.get(item_type, 'component')
                        
                        # Calcular cantidad multiplicando por la cantidad del padre
                        related_qty = supply_line.quantity * qty_parent
                        
                        # Crear movimiento para el producto relacionado
                        # CORRECCIÓN: Validar que uom_id existe antes de acceder
                        uom_id = related_product.uom_id.id if related_product.uom_id and related_product.uom_id.exists() else False
                        if not uom_id:
                            continue
                        move_vals = {
                            "name": f"{related_product.display_name} ({supply_kind} de {parent.product_id.display_name if parent.product_id else ''})",
                            "product_id": related_product.id,
                            "product_uom": uom_id,
                            "product_uom_qty": related_qty,
                            "picking_id": self.id,
                            "location_id": parent.location_id.id if parent.location_id else False,
                            "location_dest_id": parent.location_dest_id.id if parent.location_dest_id else False,
                            "company_id": parent.company_id.id if parent.company_id else False,
                            "supply_kind": supply_kind,
                            "internal_parent_move_id": parent.id,
                        }
                        
                        # SIGUE LA LÓGICA DEL MÓDULO PRODUCTIVO: Crear movimiento directamente
                        # Cada movimiento padre crea sus propios movimientos hijos sin verificar duplicados
                        # porque cada parent se procesa independientemente
                        related_move = Move.create(move_vals)
                        
                        # SIGUE LA LÓGICA DEL MÓDULO PRODUCTIVO: Crear move_line con qty_done = 0.0
                        # Esto pre-asigna el lote sin alterar el estado del picking
                        # CORRECCIÓN: Agregar quantity para evitar que Odoo elimine la línea durante la validación
                        product_uom_id = related_product.uom_id.id if related_product.uom_id and related_product.uom_id.exists() else False
                        if product_uom_id:
                            move_line_vals = {
                                "move_id": related_move.id,
                                "product_id": related_product.id,
                                "product_uom_id": product_uom_id,
                                "quantity": related_qty,  # Cantidad requerida para que Odoo no elimine la línea
                                "qty_done": 0.0,  # Sin cantidad procesada para no alterar el estado
                                "lot_id": related_lot.id,  # Pre-asignar el lote relacionado correcto
                                "location_id": parent.location_id.id if parent.location_id else False,
                                "location_dest_id": parent.location_dest_id.id if parent.location_dest_id else False,
                                "picking_id": self.id,
                            }
                            MoveLine.create(move_line_vals)
                    
                    # Continuar con el siguiente movimiento padre
                    continue

            # Si no hay lote principal con productos relacionados, usar la explosión del template
            # (comportamiento original como fallback)
            skip_complements = bool(existing_complement_moves)
            payload = _explode_of(parent, skip_complements=skip_complements)
            for kind, product, qty, uom in payload:
                if not qty or not product or not product.exists() or not uom or not uom.exists():
                    continue
                Move.create({
                    "name": f"{product.display_name} ({kind} de {parent.product_id.display_name if parent.product_id else ''})",
                    "product_id": product.id,
                    "product_uom": uom.id,
                    "product_uom_qty": qty,
                    "picking_id": self.id,
                    "location_id": parent.location_id.id if parent.location_id else False,
                    "location_dest_id": parent.location_dest_id.id if parent.location_dest_id else False,
                    "company_id": parent.company_id.id if parent.company_id else False,
                    "supply_kind": kind,
                    "internal_parent_move_id": parent.id,
                })

        return True