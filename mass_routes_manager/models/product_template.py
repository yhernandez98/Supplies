# models/product_template.py
from odoo import models, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def action_mass_select_routes(self):
        """
        Selecciona todas las rutas disponibles para los productos seleccionados.
        Si no hay productos seleccionados, aplica a todos los productos.
        """
        # Obtener todas las rutas disponibles
        all_routes = self.env['stock.route'].search([
            '|',
            ('product_selectable', '=', True),
            ('product_categ_selectable', '=', True)
        ])
        
        if not all_routes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Rutas',
                    'message': 'No se encontraron rutas disponibles en el sistema',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Aplicar rutas a los productos
        count = 0
        for record in self:
            record.route_ids = [(6, 0, all_routes.ids)]
            count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✓ Rutas Aplicadas',
                'message': f'Se seleccionaron {len(all_routes)} ruta(s) en {count} producto(s)',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_mass_deselect_routes(self):
        """
        Elimina todas las rutas de los productos seleccionados.
        Si no hay productos seleccionados, aplica a todos los productos.
        """
        count = 0
        for record in self:
            record.route_ids = [(5, 0, 0)]
            count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✗ Rutas Eliminadas',
                'message': f'Se eliminaron todas las rutas de {count} producto(s)',
                'type': 'info',
                'sticky': False,
            }
        }
