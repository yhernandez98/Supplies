# -*- coding: utf-8 -*-
from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def update_transport_rules_picking_type(self):
        """
        Actualiza todas las reglas existentes con nombre 'Salida - Transporte'
        para que tengan el picking_type_id = 43.
        
        Retorna un resumen con el número de reglas actualizadas.
        """
        # Buscar todas las reglas con nombre "Salida - Transporte"
        transport_rules = self.env['stock.rule'].search([
            ('name', '=', 'Salida - Transporte'),
        ])
        
        if not transport_rules:
            _logger.info('No se encontraron reglas "Salida - Transporte" para actualizar')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Actualización de Reglas'),
                    'message': _('No se encontraron reglas "Salida - Transporte" para actualizar.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Verificar que el tipo de operación 43 existe
        picking_type_43 = self.env['stock.picking.type'].browse(43)
        if not picking_type_43.exists():
            _logger.error('El tipo de operación con ID 43 no existe')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El tipo de operación con ID 43 no existe. Por favor, verifique que existe en el sistema.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Actualizar las reglas
        updated_count = 0
        already_updated_count = 0
        errors = []
        
        for rule in transport_rules:
            try:
                if rule.picking_type_id.id == 43:
                    already_updated_count += 1
                    _logger.info('Regla "%s" (ID: %s) ya tiene picking_type_id = 43', rule.name, rule.id)
                else:
                    old_picking_type = rule.picking_type_id.name if rule.picking_type_id else 'Sin tipo'
                    rule.write({'picking_type_id': 43})
                    updated_count += 1
                    _logger.info(
                        'Regla "%s" (ID: %s) actualizada: picking_type_id cambiado de "%s" (ID: %s) a "%s" (ID: 43)',
                        rule.name, rule.id, old_picking_type, rule.picking_type_id.id if rule.picking_type_id else 'N/A', picking_type_43.name
                    )
            except Exception as e:
                error_msg = str(e)
                errors.append(_('Regla "%s" (ID: %s): %s') % (rule.name, rule.id, error_msg))
                _logger.error('Error al actualizar regla "%s" (ID: %s): %s', rule.name, rule.id, error_msg, exc_info=True)
        
        # Preparar mensaje de resultado
        message_parts = []
        message_parts.append(_('Proceso completado:\n'))
        
        if updated_count > 0:
            message_parts.append(_('✅ Reglas actualizadas exitosamente: %s') % updated_count)
        
        if already_updated_count > 0:
            message_parts.append(_('ℹ️ Reglas que ya tenían picking_type_id = 43: %s') % already_updated_count)
        
        if errors:
            message_parts.append(_('\n❌ Errores encontrados: %s') % len(errors))
            for error in errors[:5]:  # Mostrar máximo 5 errores
                message_parts.append(f'\n- {error}')
            if len(errors) > 5:
                message_parts.append(_('\n... y %s errores más') % (len(errors) - 5))
        
        # Determinar el tipo de notificación
        if errors:
            notification_type = 'warning' if updated_count > 0 else 'danger'
        else:
            notification_type = 'success'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización de Reglas "Salida - Transporte"'),
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True,
            }
        }

