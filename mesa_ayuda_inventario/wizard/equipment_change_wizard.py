# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class EquipmentChangeWizard(models.TransientModel):
    """Wizard para crear actividad de cambio de equipo."""
    _name = 'equipment.change.wizard'
    _description = 'Wizard para Cambio de Equipo'
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        required=True,
        readonly=True,
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        readonly=True,
    )
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
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
        default='Cambio de Equipo',
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
        """Obtener valores por defecto según el contexto."""
        res = super().default_get(fields_list)
        
        # Obtener desde contexto
        lot_id = self.env.context.get('default_lot_id')
        maintenance_id = self.env.context.get('default_maintenance_id')
        partner_id = self.env.context.get('default_partner_id')
        
        if lot_id:
            lot = self.env['stock.lot'].browse(lot_id)
            res['lot_id'] = lot_id
            res['partner_id'] = lot.customer_id.id if hasattr(lot, 'customer_id') and lot.customer_id else partner_id
            res['activity_user_id'] = self.env.user.id
        
        if maintenance_id:
            maintenance = self.env['stock.lot.maintenance'].browse(maintenance_id)
            res['maintenance_id'] = maintenance_id
            if not res.get('lot_id'):
                res['lot_id'] = maintenance.lot_id.id if maintenance.lot_id else lot_id
            if not res.get('partner_id'):
                res['partner_id'] = maintenance.customer_id.id if maintenance.customer_id else res.get('partner_id')
            if maintenance.technician_ids:
                res['activity_user_id'] = maintenance.technician_ids[0].id
            elif maintenance.technician_id:
                res['activity_user_id'] = maintenance.technician_id.id
        
        # Preparar notas por defecto - más simple y claro
        if not res.get('activity_note'):
            if res.get('lot_id'):
                lot = self.env['stock.lot'].browse(res['lot_id'])
                # Mensaje muy simple y directo - solo lo esencial
                note = _('🔄 <b>Cambio de Equipo</b><br/>')
                note += _('<b>Equipo:</b> %s<br/>') % (lot.name or 'N/A')
                if hasattr(lot, 'inventory_plate') and lot.inventory_plate:
                    note += _('<b>Placa:</b> %s') % lot.inventory_plate
                
                res['activity_note'] = note
            else:
                res['activity_note'] = _('🔄 Cambio de Equipo Solicitado')
        
        return res
    
    def action_create_activity(self):
        """Crear la actividad de cambio de equipo."""
        self.ensure_one()
        
        if not self.lot_id:
            raise UserError(_('Debe seleccionar un equipo.'))
        
        # Determinar el modelo y registro al que asociar la actividad
        if self.maintenance_id:
            res_model = 'stock.lot.maintenance'
            res_id = self.maintenance_id.id
            res_name = self.maintenance_id.name or _('Mantenimiento')
        else:
            res_model = 'stock.lot'
            res_id = self.lot_id.id
            res_name = self.lot_id.name or _('Equipo')
        
        # Obtener el res_model_id desde ir.model
        model_id = self.env['ir.model'].search([('model', '=', res_model)], limit=1)
        
        # Obtener el tipo de actividad por defecto
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        activity_vals = {
            'res_model': res_model,
            'res_id': res_id,
            'res_name': res_name,
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
        
        # Crear ticket automático para cambio de equipo
        ticket = self._create_automatic_ticket()
        
        # Preparar mensaje para el chatter
        message_parts = []
        message_parts.append(_('✅ Actividad de cambio de equipo creada y asignada a %s.') % self.activity_user_id.name)
        if ticket:
            message_parts.append(_('Ticket creado automáticamente: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (ticket.id, ticket.name))
        
        message = '<br/>'.join(message_parts)
        
        # Notificar en el chatter del registro relacionado
        if self.maintenance_id:
            self.maintenance_id.message_post(
                body=message,
                subject=_('Actividad Creada')
            )
        elif self.lot_id:
            self.lot_id.message_post(
                body=message,
                subject=_('Actividad Creada')
            )
        
        # Cerrar la ventana del wizard
        return {'type': 'ir.actions.act_window_close'}
    
    def _create_automatic_ticket(self):
        """Crear ticket automático para cambio de equipo."""
        self.ensure_one()
        
        if not self.lot_id:
            return False
        
        # Obtener el cliente
        customer = self.partner_id or (self.lot_id.customer_id if hasattr(self.lot_id, 'customer_id') and self.lot_id.customer_id else False)
        
        if not customer:
            _logger.warning("No se puede crear ticket para cambio de equipo: no hay cliente asociado al equipo %s", self.lot_id.name)
            return False
        
        # Determinar si hay ticket padre (de la orden de mantenimiento)
        parent_ticket = None
        if self.maintenance_id:
            if self.maintenance_id.maintenance_order_id and self.maintenance_id.maintenance_order_id.ticket_id:
                parent_ticket = self.maintenance_id.maintenance_order_id.ticket_id
        
        # Preparar descripción del ticket con formato HTML organizado
        serial = self.lot_id.name if self.lot_id else _('N/A')
        plate = self.lot_id.inventory_plate if (self.lot_id and hasattr(self.lot_id, 'inventory_plate') and self.lot_id.inventory_plate) else _('Sin placa')
        maintenance_name = self.maintenance_id.name if (self.maintenance_id and self.maintenance_id.name) else _('N/A')
        
        ticket_description = f'''
<div style="padding: 15px; background-color: #ffe6e6; border-left: 4px solid #dc3545; border-radius: 4px; margin-bottom: 15px;">
<h3 style="color: #721c24; margin-top: 0;">🔄 Cambio de Equipo</h3>
<div style="line-height: 1.8;">
<p style="margin: 5px 0;"><strong>Equipo:</strong> {serial}</p>
<p style="margin: 5px 0;"><strong>Placa de Inventario:</strong> {plate}</p>
</div>
</div>
'''
        
        if self.activity_note:
            # Limpiar HTML básico
            import re
            note_text = self.activity_note.replace('<br/>', '\n').replace('<b>', '').replace('</b>', '')
            note_text = re.sub(r'<[^>]+>', '', note_text)
            if note_text.strip():
                ticket_description += f'''
<div style="margin-top: 15px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #0066cc; border-radius: 4px;">
<h4 style="color: #0066cc; margin-top: 0; margin-bottom: 10px;">📝 Detalles del Cambio</h4>
<p style="margin: 0; white-space: pre-wrap;">{note_text}</p>
</div>
'''
        
        if maintenance_name and maintenance_name != _('N/A'):
            ticket_description += f'''
<div style="margin-top: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 4px;">
<p style="margin: 5px 0;"><strong>Mantenimiento:</strong> {maintenance_name}</p>
</div>
'''
        
        # Preparar nombre del ticket
        ticket_name = _('Cambio de Equipo - %s') % (self.lot_id.name or 'Equipo')
        
        # Crear el ticket
        ticket_vals = {
            'name': ticket_name,
            'partner_id': customer.id,
            'description': ticket_description,
            'lot_id': self.lot_id.id,
            'maintenance_id': self.maintenance_id.id if self.maintenance_id else False,
            'maintenance_category': 'change',
            'user_id': self.activity_user_id.id if self.activity_user_id else self.env.user.id,
        }
        
        ticket = self.env['helpdesk.ticket'].create(ticket_vals)
        
        # Si hay ticket padre, vincularlos mediante mensajes
        if parent_ticket:
            parent_ticket.message_post(
                body=_('Se creó un ticket hijo para cambio de equipo: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    ticket.id, ticket.name
                ),
                subject=_('Ticket hijo creado')
            )
            ticket.message_post(
                body=_('Este ticket está relacionado con el ticket padre: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    parent_ticket.id, parent_ticket.name
                ),
                subject=_('Relación con ticket padre')
            )
        
        # Notificar en el chatter
        if self.maintenance_id:
            self.maintenance_id.message_post(
                body=_('Se creó un ticket automático para el cambio de equipo: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    ticket.id, ticket.name
                ),
                subject=_('Ticket Creado')
            )
        elif self.lot_id:
            self.lot_id.message_post(
                body=_('Se creó un ticket automático para el cambio de equipo: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    ticket.id, ticket.name
                ),
                subject=_('Ticket Creado')
            )
        
        # Cerrar el ticket automáticamente ya que el cambio ya fue realizado/solicitado
        try:
            # Buscar stage "Cerrado" o "Resuelto"
            closed_stages = self.env['helpdesk.ticket.stage'].search([
                '|',
                ('name', 'ilike', 'cerrado'),
                ('name', 'ilike', 'resuelto'),
            ], limit=1)
            if closed_stages:
                ticket.stage_id = closed_stages[0].id
            else:
                # Si no hay stage cerrado, al menos actualizar la descripción
                ticket.description = (ticket.description or '') + _('\n\n✅ Cambio de equipo procesado.')
        except Exception as e:
            _logger.warning("No se pudo cerrar automáticamente el ticket %s: %s", ticket.name, str(e))
        
        return ticket

