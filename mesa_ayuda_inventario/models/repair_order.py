# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class RepairOrder(models.Model):
    """Extensión del módulo nativo repair.order para agregar campos de mantenimiento."""
    _inherit = 'repair.order'  # ✅ Extendiendo el modelo nativo de Odoo
    
    # Solo agregamos campos que NO existen en el módulo nativo
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento Origen',
        tracking=True,
        help='Mantenimiento desde el cual se generó esta reparación'
    )
    
    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        tracking=True,
    )
    
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket Asociado',
        tracking=True,
        help='Ticket hijo creado para esta reparación'
    )
    
    # Campos adicionales para cambios de componentes (nuestro modelo personalizado)
    component_change_ids = fields.One2many(
        'repair.component.change',
        'repair_id',
        string='Componentes Cambiados',
    )
    
    def action_view_maintenance(self):
        """Ver el mantenimiento origen de esta reparación."""
        self.ensure_one()
        if not self.maintenance_id:
            raise UserError(_('Esta reparación no tiene un mantenimiento asociado.'))
        return {
            'name': _('Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot.maintenance',
            'res_id': self.maintenance_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def create_from_maintenance(self, maintenance_id):
        """Crear orden de reparación desde un mantenimiento usando el modelo nativo."""
        maintenance = self.env['stock.lot.maintenance'].browse(maintenance_id)
        problem_desc = ''
        if maintenance.observations:
            problem_desc = maintenance.observations
        elif maintenance.description:
            problem_desc = maintenance.description
        else:
            problem_desc = 'Reparación generada desde mantenimiento: ' + (maintenance.name or '')
        
        # El modelo nativo tiene sus propios campos, solo agregamos los nuestros
        repair_vals = {
            'maintenance_id': maintenance.id,
            'maintenance_order_id': maintenance.maintenance_order_id.id if maintenance.maintenance_order_id else False,
        }
        
        # Agregar campos comunes del modelo nativo (verificando que existan)
        if maintenance.lot_id:
            if hasattr(self, 'product_id') and maintenance.lot_id.product_id:
                repair_vals['product_id'] = maintenance.lot_id.product_id.id
            if hasattr(self, 'lot_id'):
                repair_vals['lot_id'] = maintenance.lot_id.id
        
        # Agregar descripción (el modelo nativo puede tener diferentes nombres de campo)
        if hasattr(self, 'description') and problem_desc:
            repair_vals['description'] = problem_desc
        elif hasattr(self, 'internal_notes') and problem_desc:
            repair_vals['internal_notes'] = problem_desc
        elif hasattr(self, 'quotation_notes') and problem_desc:
            repair_vals['quotation_notes'] = problem_desc
        
        repair = self.create(repair_vals)
        # Actualizar el mantenimiento para vincular la reparación
        maintenance.write({'repair_order_id': repair.id})
        return repair


class RepairComponentChange(models.Model):
    """Cambios de componentes en una reparación."""
    _name = 'repair.component.change'
    _description = 'Cambio de Componente en Reparación'
    
    repair_id = fields.Many2one(
        'repair.order',
        string='Orden de Reparación',
        required=True,
        ondelete='cascade',
    )
    
    old_component_lot_id = fields.Many2one(
        'stock.lot',
        string='Componente Retirado',
        help='Número de serie del componente que se retiró',
    )
    
    new_component_lot_id = fields.Many2one(
        'stock.lot',
        string='Componente Instalado',
        help='Número de serie del componente que se instaló',
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto Componente',
        required=True,
        help='Tipo de componente (ej: RAM, Disco Duro, etc.)',
    )
    
    reason = fields.Text(
        string='Motivo del Cambio',
        required=True,
    )
    
    cost = fields.Monetary(
        string='Costo',
        currency_field='currency_id',
        default=0.0,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
