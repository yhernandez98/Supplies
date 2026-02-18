# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _register_hook(self):
        """Ejecutar código cuando se carga el módulo (tanto en instalación como en actualización)."""
        res = super()._register_hook()
        # Ocultar el menú de sale_subscription y sus submenús
        # Usar un cron job o ejecutar después de que todos los módulos estén cargados
        try:
            self._hide_sale_subscription_menu()
        except Exception as e:
            _logger.error('Error en _register_hook al ocultar menús: %s', str(e))
        return res
    
    @api.model
    def load_menus(self, debug=False):
        """Sobrescribir load_menus para ocultar los menús antes de cargarlos."""
        # Ocultar los menús antes de cargarlos
        try:
            self._hide_sale_subscription_menu()
        except Exception as e:
            _logger.error('Error en load_menus al ocultar menús: %s', str(e))
        return super().load_menus(debug)

    @api.model
    def _hide_sale_subscription_menu(self):
        """Ocultar el menú 'Suscripciones' del módulo sale_subscription y sus submenús."""
        try:
            hidden_count = 0
            
            # Buscar el menú principal
            main_menu = self.env.ref('sale_subscription.menu_sale_subscription', raise_if_not_found=False)
            if not main_menu:
                _logger.warning('⚠️ No se encontró el menú principal "sale_subscription.menu_sale_subscription"')
                return False
            
            # Ocultar el menú principal
            if main_menu.active:
                main_menu.write({'active': False})
                hidden_count += 1
                _logger.info('✅ Menú principal "%s" (ID: %s) ocultado exitosamente', main_menu.name, main_menu.id)
            else:
                _logger.info('ℹ️ Menú principal "%s" (ID: %s) ya estaba oculto', main_menu.name, main_menu.id)
            
            # Buscar y ocultar todos los menús hijos (recursivamente)
            def hide_children(parent_id):
                nonlocal hidden_count
                child_menus = self.env['ir.ui.menu'].search([
                    ('parent_id', '=', parent_id)
                ])
                for child in child_menus:
                    if child.active:
                        child.write({'active': False})
                        hidden_count += 1
                        _logger.info('✅ Menú hijo "%s" (ID: %s) ocultado exitosamente', child.name, child.id)
                    # Ocultar también los hijos de este menú (recursivo)
                    hide_children(child.id)
            
            # Ocultar todos los hijos del menú principal
            hide_children(main_menu.id)
            
            if hidden_count > 0:
                self.env.cr.commit()
                _logger.info('✅ Total de menús ocultados: %s', hidden_count)
            
            return True
        except Exception as e:
            _logger.error('❌ Error al ocultar menús de sale_subscription: %s', str(e), exc_info=True)
            return False

