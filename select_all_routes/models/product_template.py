# models/product_template.py
from odoo import models

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def action_select_all_routes(self):
        """Selecciona todas las rutas de stock disponibles para los productos seleccionados."""
        self.ensure_one() # Solo se ejecuta para un registro
        all_routes = self.env['stock.route'].search([])
        # Comando (6, 0, [IDs]) = Reemplaza las rutas existentes por las nuevas
        self.write({'route_ids': [(6, 0, all_routes.ids)]})
        
        # Devuelve una acción para recargar la vista, mostrando el cambio inmediatamente
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_deselect_all_routes(self):
        """Deselecciona (elimina) todas las rutas de stock de los productos seleccionados."""
        self.ensure_one() # Solo se ejecuta para un registro
        # Comando (5, 0, 0) = Elimina todos los registros de la lista de Many2many
        self.write({'route_ids': [(5, 0, 0)]})
        
        # Devuelve una acción para recargar la vista
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
