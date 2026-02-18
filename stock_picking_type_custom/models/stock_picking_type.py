# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'
    
    @api.model
    def _post_init_update_outgoing_names(self):
        """
        Método que se puede llamar después de instalar el módulo
        para actualizar todos los nombres de tipos de operación existentes.
        """
        outgoing_types = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing')
        ])
        
        for picking_type in outgoing_types:
            if picking_type.warehouse_id:
                picking_type._update_outgoing_name()

    def _update_outgoing_name(self):
        """
        Actualiza los campos del tipo de operación de entrega (outgoing):
        - name: "ÓRDENES_DE_ENTREGA" + nombre del almacén (todo en mayúsculas, espacios con _)
        - sequence_id.name: código + "_ENTREGAS" (todo en mayúsculas, espacios con _)
        - sequence_code: "ENTREGA" + código (todo en mayúsculas, espacios con _)
        - barcode: código + "_ORDENT" (todo en mayúsculas, espacios con _)
        - default_location_src_id: ubicación "supp/transporte"
        - default_location_dest_id: ubicación de existencias del almacén (lot_stock_id)
        """
        if self.code == 'outgoing' and self.warehouse_id:
            warehouse_name = self.warehouse_id.name or ''
            warehouse_code = self.warehouse_id.code or ''
            
            # Limpiar espacios al inicio y final, convertir a mayúsculas y reemplazar espacios con _
            warehouse_name_upper = warehouse_name.strip().upper().replace(' ', '_')
            # Eliminar guiones bajos al final
            warehouse_name_upper = warehouse_name_upper.rstrip('_')
            
            # Limpiar espacios al inicio y final, convertir a mayúsculas y reemplazar espacios con _
            warehouse_code_upper = warehouse_code.strip().upper().replace(' ', '_') if warehouse_code else ''
            # Eliminar guiones bajos al final
            warehouse_code_upper = warehouse_code_upper.rstrip('_')
            
            # Actualizar el nombre del tipo de operación: "ÓRDENES_DE_ENTREGA" + nombre del almacén
            if warehouse_name_upper:
                self.name = f'ÓRDENES_DE_ENTREGA_{warehouse_name_upper}'.rstrip('_')
            else:
                self.name = 'ÓRDENES_DE_ENTREGA'
            
            # Actualizar el nombre de la secuencia (sequence_id): código + "_ENTREGAS"
            if self.sequence_id:
                if warehouse_code_upper:
                    # Limpiar espacios y guiones bajos al inicio y final
                    sequence_name = f'{warehouse_code_upper}_ENTREGAS'.strip().rstrip('_')
                else:
                    sequence_name = 'ENTREGAS'
                # Asegurarse de que no haya espacios en blanco
                sequence_name = sequence_name.replace(' ', '_').strip()
                self.sequence_id.write({
                    'name': sequence_name
                })
            
            # Actualizar el código de la secuencia (sequence_code): "ENTREGA" + código
            if warehouse_code_upper:
                self.sequence_code = f'ENTREGA_{warehouse_code_upper}'.rstrip('_')
            else:
                self.sequence_code = 'ENTREGA'
            
            # Actualizar el código de barras (barcode): código + "_ORDENT"
            if warehouse_code_upper:
                self.barcode = f'{warehouse_code_upper}_ORDENT'.rstrip('_')
            else:
                self.barcode = 'ORDENT'
            
            # Actualizar la ubicación de origen (default_location_src_id): "supp/transporte"
            # Buscar la ubicación por complete_name (ruta completa)
            transport_location = self.env['stock.location'].search([
                ('complete_name', '=', 'supp/transporte')
            ], limit=1)
            
            if not transport_location:
                # Intentar buscar con diferentes variaciones (mayúsculas/minúsculas)
                transport_location = self.env['stock.location'].search([
                    '|',
                    ('complete_name', 'ilike', 'supp/transporte'),
                    ('complete_name', 'ilike', 'Supplies/Transporte'),
                ], limit=1)
            
            if transport_location:
                self.default_location_src_id = transport_location.id
            else:
                # Si no se encuentra, registrar un warning pero no fallar
                # El usuario puede configurarlo manualmente
                pass
            
            # Actualizar la ubicación de destino (default_location_dest_id): ubicación de existencias del almacén
            # La ubicación de existencias del almacén se accede a través de lot_stock_id
            if self.warehouse_id.lot_stock_id:
                self.default_location_dest_id = self.warehouse_id.lot_stock_id.id
            else:
                # Si no tiene ubicación de stock, intentar buscar la ubicación principal del almacén
                # Esto es un fallback, normalmente lot_stock_id debería existir
                pass
        
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe el método create para actualizar el nombre
        automáticamente cuando se crea un tipo de operación de tipo "outgoing".
        """
        picking_types = super().create(vals_list)
        
        for picking_type in picking_types:
            if picking_type.code == 'outgoing' and picking_type.warehouse_id:
                picking_type._update_outgoing_name()
        
        return picking_types

    def write(self, vals):
        """
        Sobrescribe el método write para actualizar el nombre
        automáticamente cuando se modifica un tipo de operación de tipo "outgoing"
        y cambia el almacén asociado.
        """
        result = super().write(vals)
        
        # Si se actualiza el warehouse_id o el code, actualizar el nombre
        if 'warehouse_id' in vals or 'code' in vals:
            for picking_type in self:
                if picking_type.code == 'outgoing' and picking_type.warehouse_id:
                    picking_type._update_outgoing_name()
        
        return result

    @api.model
    def action_update_all_outgoing_names(self):
        """
        Actualiza todos los campos de los tipos de operación de tipo "outgoing":
        - name: "ÓRDENES_DE_ENTREGA" + nombre del almacén
        - sequence_id.name: código + "_ENTREGAS"
        - sequence_code: "ENTREGA" + código
        - barcode: código + "_ORDENT"
        - default_location_src_id: ubicación "supp/transporte"
        - default_location_dest_id: ubicación de existencias del almacén (lot_stock_id)
        
        Retorna un resumen con el número de tipos de operación actualizados.
        """
        # Buscar todos los tipos de operación de tipo "outgoing"
        outgoing_types = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing')
        ])
        
        if not outgoing_types:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No hay tipos de operación para actualizar'),
                    'message': _(
                        'No se encontraron tipos de operación de tipo "outgoing" para actualizar.'
                    ),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        updated_count = 0
        error_count = 0
        location_not_found_count = 0
        errors = []
        location_warnings = []
        
        # Buscar la ubicación "supp/transporte" una sola vez
        transport_location = self.env['stock.location'].search([
            ('complete_name', '=', 'supp/transporte')
        ], limit=1)
        
        if not transport_location:
            # Intentar buscar con diferentes variaciones (mayúsculas/minúsculas)
            transport_location = self.env['stock.location'].search([
                '|',
                ('complete_name', 'ilike', 'supp/transporte'),
                ('complete_name', 'ilike', 'Supplies/Transporte'),
            ], limit=1)
        
        if not transport_location:
            location_warnings.append(_(
                '⚠️ No se encontró la ubicación "supp/transporte". '
                'Por favor, verifique que la ubicación existe en el sistema.'
            ))
        
        for picking_type in outgoing_types:
            try:
                if picking_type.warehouse_id:
                    # Actualizar todos los campos
                    picking_type._update_outgoing_name()
                    
                    # Si se encontró la ubicación, actualizarla también
                    if transport_location and not picking_type.default_location_src_id or \
                       (picking_type.default_location_src_id and picking_type.default_location_src_id != transport_location):
                        picking_type.default_location_src_id = transport_location.id
                    elif not transport_location:
                        location_not_found_count += 1
                    
                    updated_count += 1
                else:
                    errors.append(_(
                        'Tipo de operación "%s" (ID: %s): No tiene almacén asociado'
                    ) % (picking_type.name, picking_type.id))
                    error_count += 1
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                if picking_type.name:
                    errors.append(_(
                        'Tipo de operación "%s" (ID: %s): %s'
                    ) % (picking_type.name, picking_type.id, error_msg))
                else:
                    errors.append(_(
                        'Tipo de operación (ID: %s): %s'
                    ) % (picking_type.id, error_msg))
        
        # Preparar mensaje de resultado
        message_parts = []
        message_parts.append(_('Proceso completado:\n'))
        message_parts.append(_('✅ Tipos de operación actualizados exitosamente: %s') % updated_count)
        
        if location_warnings:
            for warning in location_warnings:
                message_parts.append(f'\n{warning}')
        
        if location_not_found_count > 0 and not transport_location:
            message_parts.append(_(
                '\n⚠️ %s tipos de operación no pudieron actualizar la ubicación de origen '
                '(ubicación "supp/transporte" no encontrada)'
            ) % location_not_found_count)
        
        if error_count > 0:
            message_parts.append(_('\n❌ Errores encontrados: %s') % error_count)
            if errors:
                message_parts.append(_('\n\nErrores detallados:'))
                for error in errors[:10]:  # Mostrar máximo 10 errores
                    message_parts.append(f'\n- {error}')
                if len(errors) > 10:
                    message_parts.append(_('\n... y %s errores más') % (len(errors) - 10))
        
        # Determinar el tipo de notificación
        notification_type = 'success' if error_count == 0 else 'warning' if updated_count > 0 else 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización de Nombres de Tipos de Operación'),
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True,
            }
        }

