# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ActivityAssignmentWizard(models.TransientModel):
    """Wizard para asignar actividad de reparación a un usuario específico."""
    _name = 'activity.assignment.wizard'
    _description = 'Wizard para Asignar Actividad'
    
    repair_order_id = fields.Many2one(
        'repair.order',
        string='Orden de Reparación',
        required=True,
        readonly=True,
    )
    
    activity_user_id = fields.Many2one(
        'res.users',
        string='Asignar Actividad a',
        required=True,
        help='Usuario al que se asignará la actividad'
    )
    
    activity_summary = fields.Char(
        string='Resumen',
        required=True,
        default='Nueva orden de reparación creada desde mantenimiento',
        help='Resumen de la actividad'
    )
    
    activity_note = fields.Html(
        string='Notas',
        help='Notas adicionales para la actividad'
    )
    
    activity_date_deadline = fields.Datetime(
        string='Fecha Límite',
        default=fields.Datetime.now,
        required=True,
    )
    
    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto."""
        res = super().default_get(fields_list)
        
        repair_order_id = self.env.context.get('default_repair_order_id')
        maintenance_id = self.env.context.get('default_maintenance_id')
        
        if repair_order_id:
            repair_order = self.env['repair.order'].browse(repair_order_id)
            res['repair_order_id'] = repair_order_id
            
            # Obtener técnico por defecto desde el mantenimiento
            if maintenance_id:
                maintenance = self.env['stock.lot.maintenance'].browse(maintenance_id)
                if maintenance.technician_ids:
                    res['activity_user_id'] = maintenance.technician_ids[0].id
                elif maintenance.technician_id:
                    res['activity_user_id'] = maintenance.technician_id.id
            
            # Preparar notas por defecto
            if not res.get('activity_note'):
                note = _('Se creó una orden de reparación desde el mantenimiento.\n\nOrden de Reparación: %s') % (repair_order.name or '')
                res['activity_note'] = note
        
        return res
    
    def action_create_activity(self):
        """Crear la actividad con el usuario seleccionado."""
        self.ensure_one()
        
        if not self.repair_order_id:
            raise UserError(_('Debe seleccionar una orden de reparación.'))
        
        # Obtener el res_model_id desde ir.model
        res_model = 'repair.order'
        model_id = self.env['ir.model'].search([('model', '=', res_model)], limit=1)
        
        # Obtener el tipo de actividad por defecto
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        activity_vals = {
            'res_model': res_model,
            'res_id': self.repair_order_id.id,
            'res_name': self.repair_order_id.name or _('Nueva Reparación'),
            'summary': self.activity_summary,
            'note': self.activity_note,
            'user_id': self.activity_user_id.id,
            'date_deadline': self.activity_date_deadline,
        }
        
        # Agregar res_model_id si se encontró el modelo
        if model_id:
            activity_vals['res_model_id'] = model_id.id
        
        # Agregar activity_type_id si existe
        if activity_type:
            activity_vals['activity_type_id'] = activity_type.id
        
        activity = self.env['mail.activity'].create(activity_vals)
        
        # Redirigir a la reparación después de crear la actividad
        return {
            'name': _('Orden de Reparación'),
            'type': 'ir.actions.act_window',
            'res_model': 'repair.order',
            'res_id': self.repair_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

