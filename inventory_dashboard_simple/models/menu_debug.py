# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MenuDebug(models.TransientModel):
    """Modelo temporal para debug de menús."""
    _name = 'inventory.menu.debug'
    _description = 'Debug de Menús de Inventario'

    def action_show_menu_info(self):
        """Mostrar información de todos los menús hijos de Inventario."""
        self.ensure_one()
        
        try:
            stock_root = self.env.ref('stock.menu_stock_root')
            
            # Obtener todos los menús hijos
            all_menus = self.env['ir.ui.menu'].search([
                ('parent_id', '=', stock_root.id)
            ], order='sequence')
            
            # Construir mensaje con toda la información
            message_lines = ['=== MENÚS HIJOS DE INVENTARIO ===\n']
            
            for m in all_menus:
                # Obtener ID externo
                external_id = self.env['ir.model.data'].search([
                    ('model', '=', 'ir.ui.menu'),
                    ('res_id', '=', m.id)
                ], limit=1)
                external_id_str = external_id.complete_name if external_id else 'Sin ID externo'
                
                # Obtener información de la acción si existe
                action_info = 'Sin acción'
                if m.action:
                    action_info = str(m.action)
                
                message_lines.append(
                    f'📋 {m.name}\n'
                    f'   ID: {m.id}\n'
                    f'   Secuencia: {m.sequence}\n'
                    f'   ID Externo: {external_id_str}\n'
                    f'   Acción: {action_info}\n'
                    f'   Activo: {m.active}\n'
                )
            
            message = '\n'.join(message_lines)
            
            # Mostrar en un diálogo
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información de Menús de Inventario'),
                    'message': message,
                    'type': 'info',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            raise UserError(_('Error al obtener información de menús: %s') % str(e))

