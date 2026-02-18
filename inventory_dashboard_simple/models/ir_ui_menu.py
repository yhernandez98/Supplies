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
        # Ocultar el menú "Información general" cada vez que se carga el módulo
        self._hide_stock_overview_menu()
        return res

    @api.model
    def _hide_stock_overview_menu(self):
        """Ocultar el menú 'Información general' del módulo stock."""
        try:
            # Buscar el menú por su ID externo
            menu = self.env.ref('stock.stock_picking_type_menu', raise_if_not_found=False)
            if menu and menu.active:
                menu.write({'active': False})
                # No hacer commit manual - Odoo maneja las transacciones automáticamente
                _logger.info('✅ Menú "Información general" (ID: %s) ocultado exitosamente', menu.id)
                return True
            elif menu and not menu.active:
                _logger.info('ℹ️ Menú "Información general" ya estaba oculto')
                return True
            else:
                _logger.warning('⚠️ No se encontró el menú "Información general" (stock.stock_picking_type_menu)')
                return False
        except Exception as e:
            _logger.error('❌ Error al ocultar el menú "Información general": %s', str(e), exc_info=True)
            return False

