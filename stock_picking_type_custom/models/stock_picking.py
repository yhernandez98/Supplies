# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_moves_without_package(self):
        """Odoo 18: move_ids_without_package; Odoo 19+: move_ids."""
        return getattr(self, 'move_ids_without_package', None) or self.move_ids

    def _check_and_update_picking_type_for_transport_route(self):
        """
        Verifica si alguna ruta asociada tiene la regla 'Salida - Transporte'
        y actualiza automáticamente el picking_type_id a 43.
        
        IMPORTANTE: NO actualiza pickings de recepción (incoming) para evitar
        que se cambien a transporte cuando se guardan o actualizan.
        
        OPTIMIZADO: Verificaciones tempranas para evitar búsquedas costosas.
        """
        # OPTIMIZACIÓN: Verificaciones tempranas (ya se hacen en write(), pero por seguridad)
        # Solo actualizar si el picking no está en estado final
        if self.state in ('done', 'cancel'):
            return False
        
        # IMPORTANTE: NO actualizar pickings de recepción (incoming)
        # Esto previene que las órdenes de recepción se cambien a transporte
        if self.picking_type_id and self.picking_type_id.code == 'incoming':
            return False
        
        # También verificar si tiene purchase_id (es una recepción)
        if self.purchase_id:
            return False
        
        # OPTIMIZACIÓN: Si ya es tipo 43, no hacer nada
        if self.picking_type_id.id == 43:
            return False
        
        # OPTIMIZACIÓN: Verificar que tenga movimientos antes de iterar
        if not self._get_moves_without_package():
            return False
        
        # OPTIMIZACIÓN: Verificar que el tipo de operación 43 existe UNA SOLA VEZ al inicio
        # (en lugar de hacerlo después de todas las búsquedas)
        picking_type_43 = self.env['stock.picking.type'].browse(43)
        if not picking_type_43.exists():
            _logger.warning('El tipo de operación con ID 43 no existe. No se puede actualizar el picking %s', self.name)
            return False
        
        # Buscar si alguno de los movimientos tiene una ruta con la regla "Salida - Transporte"
        routes_to_check = set()
        
        # OPTIMIZACIÓN: Usar mapped() para obtener rutas de forma más eficiente
        # Obtener rutas de los productos de los movimientos
        moves = self._get_moves_without_package()
        product_routes = moves.mapped('product_id.route_ids')
        if product_routes:
            routes_to_check.update(product_routes.ids)
        
        # También verificar rutas de la orden de venta si existe
        sale_routes = moves.filtered('sale_line_id.order_id.route_id').mapped('sale_line_id.order_id.route_id')
        if sale_routes:
            routes_to_check.update(sale_routes.ids)
        
        if not routes_to_check:
            return False
        
        # OPTIMIZACIÓN: Usar search_count en lugar de search cuando solo necesitamos saber si existe
        has_transport_rule = self.env['stock.rule'].search_count([
            ('route_id', 'in', list(routes_to_check)),
            ('name', '=', 'Salida - Transporte'),
        ], limit=1) > 0
        
        if not has_transport_rule:
            return False
        
        # Actualizar el picking_type_id a 43
        # OPTIMIZACIÓN: Usar contexto para evitar recursión (skip_transport_check)
        self.with_context(skip_transport_check=True).write({'picking_type_id': 43})
        _logger.info('Picking %s actualizado automáticamente: picking_type_id cambiado a 43 (Salida - Transporte)', self.name)
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
                # OPTIMIZACIÓN 1: Verificaciones tempranas antes de hacer búsquedas costosas
                # NO actualizar si es un picking de recepción
                if picking.picking_type_id and picking.picking_type_id.code == 'incoming':
                    continue
                if picking.purchase_id:
                    continue
                
                # OPTIMIZACIÓN 2: Si ya es tipo 43, no verificar (evita búsquedas innecesarias)
                if picking.picking_type_id.id == 43:
                    continue
                
                # OPTIMIZACIÓN 3: Si está en estado final, no verificar
                if picking.state in ('done', 'cancel'):
                    continue
                
                # OPTIMIZACIÓN 4: Solo verificar si tiene movimientos (evita búsquedas en pickings vacíos)
                if not picking._get_moves_without_package():
                    continue
                
                # Solo ahora hacer la verificación costosa
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
            routes_to_check = set()
            
            # Obtener rutas de los productos de los movimientos
            for move in picking._get_moves_without_package():
                if move.product_id and move.product_id.route_ids:
                    product_routes = move.product_id.route_ids.filtered(lambda r: r.id in route_ids)
                    if product_routes:
                        routes_to_check.update(product_routes.ids)
                
                # También verificar rutas de la orden de venta si existe
                if move.sale_line_id and move.sale_line_id.order_id and move.sale_line_id.order_id.route_id:
                    if move.sale_line_id.order_id.route_id.id in route_ids:
                        routes_to_check.add(move.sale_line_id.order_id.route_id.id)
            
            # Si se encontraron rutas con la regla "Salida - Transporte", actualizar
            if routes_to_check:
                # Verificar que realmente tenga la regla
                has_transport_rule = self.env['stock.rule'].search_count([
                    ('route_id', 'in', list(routes_to_check)),
                    ('name', '=', 'Salida - Transporte'),
                ]) > 0
                
                if has_transport_rule:
                    picking.write({'picking_type_id': 43})
                    updated_count += 1
                    _logger.info('Picking %s actualizado: picking_type_id cambiado a 43', picking.name)
        
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

