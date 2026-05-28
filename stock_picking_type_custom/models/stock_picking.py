# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)

# ID fijo del tipo «Salida - Transporte» (histórico en Supplies).
TRANSPORT_PICKING_TYPE_ID = 43


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _is_devolucion_operation_type(self):
        """True si el tipo de operación actual es de devolución (cliente → almacén)."""
        self.ensure_one()
        if not self.picking_type_id:
            return False
        name = (self.picking_type_id.name or '').lower()
        return 'devoluc' in name

    def _origin_indicates_devolucion_route(self):
        """True si el origin del picking pertenece a una ruta de devolución (wizard rutas)."""
        self.ensure_one()
        origin = (self.origin or '').lower()
        return 'devolucion' in origin or 'devolución' in origin

    def _should_skip_transport_type_auto_update(self):
        """
        No forzar tipo Transporte (43) en devoluciones ni en la primera etapa de una ruta.
        Evita salir del flujo RECIEND Devoluciones al guardar líneas en Operaciones.
        """
        self.ensure_one()
        if self._is_devolucion_operation_type():
            return True
        if self._origin_indicates_devolucion_route():
            return True
        # Primera etapa del wizard (…-E1): aún no es Salida → Transporte
        if self.origin and re.search(r'[\s-]E1\s*$', self.origin, re.IGNORECASE):
            return True
        return False

    def _get_routes_from_picking_origin(self):
        """Ruta asociada al origin (Ruta-…-W…-E#), no todas las rutas del producto."""
        self.ensure_one()
        Route = self.env['stock.route']
        origin = (self.origin or '').strip()
        if not origin.startswith('Ruta-'):
            return Route.browse()
        base = origin.split('-E')[0]
        route_key = base.replace('Ruta-', '', 1)
        if not route_key:
            return Route.browse()
        # El wizard trunca el nombre de ruta a 25 caracteres al armar el origin
        prefix = route_key
        if '-W' in route_key:
            prefix = route_key.rsplit('-W', 1)[0]
        candidates = Route.search([
            '|',
            ('name', 'ilike', prefix),
            ('name', 'ilike', prefix[:25]),
        ], limit=5)
        return candidates

    def _picking_is_salida_transport_leg(self):
        """True si ubicaciones del picking coinciden con etapa Salida → Transporte."""
        self.ensure_one()
        if not self.location_id or not self.location_dest_id:
            return False
        src = (self.location_id.complete_name or self.location_id.name or '').lower()
        dest = (self.location_dest_id.complete_name or self.location_dest_id.name or '').lower()
        return 'salida' in src and 'transporte' in dest

    def _transport_rule_applies_to_this_picking(self, rule):
        """La regla Salida - Transporte solo aplica si el picking ES esa etapa (ubicaciones)."""
        self.ensure_one()
        if rule.name != 'Salida - Transporte':
            return False
        pt = rule.picking_type_id
        loc_src = rule.location_src_id or (pt.default_location_src_id if pt else False)
        loc_dest = rule.location_dest_id or (pt.default_location_dest_id if pt else False)
        if loc_src and loc_dest:
            return (
                self.location_id.id == loc_src.id
                and self.location_dest_id.id == loc_dest.id
            )
        return self._picking_is_salida_transport_leg()

    def _get_moves_for_route_check(self):
        """Odoo 19: move_ids_without_package fue eliminado; usar move_ids."""
        return getattr(self, 'move_ids_without_package', self.move_ids)

    @api.model
    def _get_routes_from_sale_moves(self, moves):
        """Rutas ligadas a movimientos de venta (compatible Odoo 19 sin route_id en pedido)."""
        Route = self.env['stock.route']
        sale_moves = moves.filtered('sale_line_id')
        if not sale_moves:
            return Route.browse()

        SaleOrder = self.env['sale.order']
        SaleLine = self.env['sale.order.line']
        routes = Route.browse()

        if 'route_id' in SaleOrder._fields:
            routes |= sale_moves.mapped('sale_line_id.order_id.route_id')

        if 'route_id' in SaleLine._fields:
            routes |= sale_moves.mapped('sale_line_id.route_id')

        return routes.filtered(lambda r: r)

    def _check_and_update_picking_type_for_transport_route(self):
        """
        Verifica si el picking corresponde a la etapa «Salida - Transporte» de SU ruta
        y actualiza picking_type_id a 43 solo en ese caso.

        No usa todas las rutas del producto (evita pisar devoluciones al guardar líneas).
        No toca recepciones ni pickings de devolución (tipo u origin).
        """
        self.ensure_one()

        if self.state in ('done', 'cancel'):
            return False

        if self.picking_type_id and self.picking_type_id.code == 'incoming':
            return False

        if self.purchase_id:
            return False

        if self._should_skip_transport_type_auto_update():
            _logger.debug(
                'Picking %s: omitido auto-tipo Transporte (devolución u etapa inicial de ruta)',
                self.name,
            )
            return False

        if self.picking_type_id.id == TRANSPORT_PICKING_TYPE_ID:
            return False

        moves = self._get_moves_for_route_check()
        if not moves:
            return False

        picking_type_43 = self.env['stock.picking.type'].browse(TRANSPORT_PICKING_TYPE_ID)
        if not picking_type_43.exists():
            _logger.warning(
                'El tipo de operación con ID %s no existe. No se puede actualizar el picking %s',
                TRANSPORT_PICKING_TYPE_ID, self.name,
            )
            return False

        routes_to_check = self._get_routes_from_picking_origin()
        if not routes_to_check:
            # Sin origin de ruta: solo ventas o leg Salida→Transporte ya visible en ubicaciones
            if self._picking_is_salida_transport_leg():
                sale_routes = self._get_routes_from_sale_moves(moves)
                if sale_routes:
                    routes_to_check = sale_routes
            else:
                return False

        transport_rules = self.env['stock.rule'].search([
            ('route_id', 'in', routes_to_check.ids),
            ('name', '=', 'Salida - Transporte'),
        ])
        applicable = transport_rules.filtered(
            lambda r: self._transport_rule_applies_to_this_picking(r)
        )
        if not applicable:
            return False

        self.with_context(skip_transport_check=True).write({
            'picking_type_id': TRANSPORT_PICKING_TYPE_ID,
        })
        _logger.info(
            'Picking %s: tipo de operación actualizado a %s (etapa Salida - Transporte)',
            self.name, picking_type_43.name,
        )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe el método create para actualizar automáticamente
        el picking_type_id cuando se detecta la regla 'Salida - Transporte'.
        
        También maneja errores de nombre duplicado regenerando el nombre automáticamente.
        """
        # Intentar crear los pickings normalmente
        try:
            pickings = super().create(vals_list)
        except Exception as e:
            # Si hay un error de nombre duplicado, intentar regenerar los nombres
            error_str = str(e)
            is_unique_violation = (
                'stock_picking_name_uniq' in error_str or 
                'duplicate key value violates unique constraint' in error_str.lower() or
                'UniqueViolation' in str(type(e).__name__)
            )
            
            if is_unique_violation:
                _logger.warning("Error de nombre duplicado al crear picking, regenerando nombres automáticamente: %s", error_str)
                
                # IMPORTANTE: Hacer rollback de la transacción abortada antes de reintentar
                # PostgreSQL marca la transacción como "aborted" después de un error
                # Necesitamos hacer rollback para poder ejecutar más comandos
                try:
                    # Verificar si la transacción está abortada intentando ejecutar un comando simple
                    self.env.cr.execute("SELECT 1")
                except Exception:
                    # Si falla, la transacción está abortada, hacer rollback
                    try:
                        self.env.cr.rollback()
                        _logger.info("Rollback de transacción abortada completado")
                    except Exception as rollback_error:
                        _logger.warning("Error al hacer rollback: %s", str(rollback_error))
                        # Si el rollback falla, limpiar el entorno
                        try:
                            self.env.clear()
                        except:
                            pass
                
                # Para cada vals, eliminar el nombre si existe para forzar regeneración
                # Esto hará que Odoo genere un nuevo nombre desde la secuencia
                for vals in vals_list:
                    if 'name' in vals:
                        old_name = vals.get('name')
                        _logger.info("Eliminando nombre '%s' para forzar regeneración desde secuencia", old_name)
                        del vals['name']
                
                # Intentar crear nuevamente sin nombres (Odoo los generará automáticamente desde la secuencia)
                # La secuencia debería avanzar y generar un nombre único
                try:
                    pickings = super().create(vals_list)
                    _logger.info("Pickings creados exitosamente después de regenerar nombres desde secuencia")
                except Exception as e2:
                    error_str2 = str(e2)
                    _logger.error("Error al crear pickings después de regenerar nombres: %s", error_str2)
                    
                    # Si es el mismo error, la secuencia está realmente desincronizada
                    if 'stock_picking_name_uniq' in error_str2 or 'duplicate key value violates unique constraint' in error_str2.lower():
                        _logger.error("La secuencia de nombres de picking está desincronizada. Se requiere intervención manual en la base de datos.")
                        # Hacer rollback antes de re-lanzar
                        try:
                            self.env.cr.rollback()
                        except:
                            pass
                        raise UserError(_(
                            'Error al crear el picking: La secuencia de nombres está desincronizada. '
                            'Por favor, contacte al administrador del sistema para corregir la secuencia de nombres de picking.'
                        ))
                    else:
                        # Otro tipo de error, re-lanzarlo
                        try:
                            self.env.cr.rollback()
                        except:
                            pass
                        raise
            else:
                # Si es otro tipo de error, re-lanzarlo
                raise
        
        for picking in pickings:
            # Verificar y actualizar después de crear los movimientos
            # Usar un método diferido para asegurar que los movimientos estén creados
            picking._check_and_update_picking_type_for_transport_route()
        
        return pickings

    def write(self, vals):
        """
        Sobrescribe el método write para actualizar automáticamente
        el picking_type_id cuando se detecta la regla 'Salida - Transporte'.
        
        IMPORTANTE: NO actualiza pickings de recepción (incoming).
        OPTIMIZADO: Solo verifica cuando es realmente necesario.
        """
        # Evitar actualizaciones recursivas (cuando este método se llama desde _check_and_update)
        if self.env.context.get('skip_transport_check'):
            return super().write(vals)
        
        result = super().write(vals)
        
        # Solo verificar si realmente se modificaron movimientos
        if 'move_ids_without_package' in vals or 'move_ids' in vals:
            for picking in self:
                if picking.picking_type_id and picking.picking_type_id.code == 'incoming':
                    continue
                if picking.purchase_id:
                    continue
                if picking._should_skip_transport_type_auto_update():
                    continue
                if picking.picking_type_id.id == TRANSPORT_PICKING_TYPE_ID:
                    continue
                if picking.state in ('done', 'cancel'):
                    continue
                if not picking._get_moves_for_route_check():
                    continue
                picking.with_context(skip_transport_check=True)._check_and_update_picking_type_for_transport_route()
        
        return result

    @api.model
    def update_existing_pickings_for_transport_route(self):
        """
        Actualiza todos los pickings existentes que tengan una ruta con la regla 'Salida - Transporte'
        y que aún no tengan el picking_type_id = 43.
        
        Este método puede ser llamado desde warehouse_auto_create cuando se crean nuevas rutas.
        """
        # Buscar todas las reglas "Salida - Transporte"
        transport_rules = self.env['stock.rule'].search([
            ('name', '=', 'Salida - Transporte'),
        ])
        
        if not transport_rules:
            _logger.info('No se encontraron reglas "Salida - Transporte" para actualizar pickings')
            return {
                'updated': 0,
                'message': _('No se encontraron reglas "Salida - Transporte"')
            }
        
        # Obtener todas las rutas asociadas a estas reglas
        route_ids = transport_rules.mapped('route_id').ids
        
        if not route_ids:
            _logger.info('No se encontraron rutas asociadas a las reglas "Salida - Transporte"')
            return {
                'updated': 0,
                'message': _('No se encontraron rutas asociadas')
            }
        
        # Buscar pickings que:
        # 1. Tengan movimientos con productos que tengan estas rutas
        # 2. O tengan movimientos de órdenes de venta con estas rutas
        # 3. No estén en estado final
        # 4. No tengan ya el picking_type_id = 43
        
        updated_count = 0
        picking_type_43 = self.env['stock.picking.type'].browse(43)
        
        if not picking_type_43.exists():
            _logger.warning('El tipo de operación con ID 43 no existe')
            return {
                'updated': 0,
                'message': _('El tipo de operación con ID 43 no existe')
            }
        
        # Buscar pickings que tengan movimientos con productos que usen estas rutas
        # IMPORTANTE: Excluir pickings de recepción (incoming)
        all_pickings = self.env['stock.picking'].search([
            ('state', 'not in', ('done', 'cancel')),
            ('picking_type_id', '!=', 43),
        ])
        
        # Filtrar para excluir pickings de recepción
        pickings_to_update = all_pickings.filtered(
            lambda p: p.picking_type_id.code != 'incoming' and not p.purchase_id
        )
        
        for picking in pickings_to_update:
            if picking._should_skip_transport_type_auto_update():
                continue
            routes = picking._get_routes_from_picking_origin()
            if not routes:
                continue
            routes = routes.filtered(lambda r: r.id in route_ids)
            if not routes:
                continue
            transport_rules = self.env['stock.rule'].search([
                ('route_id', 'in', routes.ids),
                ('name', '=', 'Salida - Transporte'),
            ])
            if transport_rules.filtered(
                lambda r: picking._transport_rule_applies_to_this_picking(r)
            ):
                picking.write({'picking_type_id': TRANSPORT_PICKING_TYPE_ID})
                updated_count += 1
                _logger.info('Picking %s actualizado: picking_type_id cambiado a %s', picking.name, TRANSPORT_PICKING_TYPE_ID)
        
        _logger.info('Actualización masiva completada: %s pickings actualizados', updated_count)
        
        return {
            'updated': updated_count,
            'message': _('Se actualizaron %s pickings exitosamente') % updated_count
        }

    def action_update_picking_type_for_transporte_route(self):
        """
        Método llamado desde el botón en la vista.
        Actualiza el tipo de operación del picking a "Salida - Transporte" (ID: 43)
        si tiene una ruta con la regla 'Salida - Transporte'.
        
        Este método es llamado desde un botón en la vista que está siendo ocultado.
        Se mantiene por compatibilidad en caso de que se llame desde otro lugar.
        """
        self.ensure_one()
        
        # Verificar que no esté en estado final
        if self.state in ('done', 'cancel'):
            raise UserError(_('No se puede actualizar el tipo de operación de un picking en estado final.'))
        
        # Verificar que no sea un picking de recepción
        if self.picking_type_id and self.picking_type_id.code == 'incoming':
            raise UserError(_('No se puede actualizar el tipo de operación de un picking de recepción.'))
        
        if self.purchase_id:
            raise UserError(_('No se puede actualizar el tipo de operación de un picking de recepción.'))
        
        # Llamar al método privado que hace la verificación y actualización
        result = self._check_and_update_picking_type_for_transport_route()
        
        if result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tipo de operación actualizado'),
                    'message': _('El tipo de operación se ha actualizado a "Salida - Transporte".'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin cambios'),
                    'message': _('El picking no tiene rutas con la regla "Salida - Transporte" o ya tiene el tipo de operación correcto.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

