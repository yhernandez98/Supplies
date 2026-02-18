# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
import base64
import re
import traceback

_logger = logging.getLogger(__name__)


class MaintenanceOrder(models.Model):
    """Orden de Mantenimiento que agrupa múltiples mantenimientos de equipos."""
    _name = 'maintenance.order'
    _description = 'Orden de Mantenimiento'
    _order = 'scheduled_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de Orden',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
        help='Número único de la orden de mantenimiento'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        help='Cliente para el cual se realizará el mantenimiento'
    )
    
    technician_ids = fields.Many2many(
        'res.users',
        'maintenance_order_technician_rel',
        'order_id',
        'user_id',
        string='Técnicos Asignados',
        default=lambda self: [(6, 0, [self.env.user.id])] if self.env.user else False,
        tracking=True,
        help='Técnicos responsables de realizar el mantenimiento'
    )
    
    scheduled_date = fields.Datetime(
        string='Fecha Programada',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Fecha y hora programada para realizar el mantenimiento'
    )
    
    deadline_date = fields.Datetime(
        string='Fecha Límite',
        tracking=True,
        help='Fecha límite para completar el mantenimiento'
    )
    
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('scheduled', 'Programada'),
            ('in_progress', 'En Progreso'),
            ('completed', 'Completada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        required=True,
        tracking=True,
        help='Estado de la orden de mantenimiento'
    )
    
    maintenance_ids = fields.One2many(
        'stock.lot.maintenance',
        'maintenance_order_id',
        string='Mantenimientos',
        help='Mantenimientos individuales de cada equipo'
    )
    
    # ✅ Campo computed para mostrar todos los cambios de componentes de los mantenimientos asociados
    all_component_change_ids = fields.One2many(
        'maintenance.component.change',
        string='Todos los Cambios de Componentes',
        compute='_compute_all_component_changes',
        help='Todos los cambios de componentes de los mantenimientos en esta orden'
    )
    
    @api.depends('maintenance_ids.component_change_ids')
    def _compute_all_component_changes(self):
        """Calcular todos los cambios de componentes de los mantenimientos asociados."""
        for order in self:
            all_changes = self.env['maintenance.component.change']
            for maintenance in order.maintenance_ids:
                all_changes |= maintenance.component_change_ids
            order.all_component_change_ids = all_changes
    
    maintenance_count = fields.Integer(
        string='Cantidad de Mantenimientos',
        compute='_compute_maintenance_count',
        store=True
    )
    
    completed_maintenance_count = fields.Integer(
        string='Mantenimientos Completados',
        compute='_compute_maintenance_count',
        store=True
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción general de la orden de mantenimiento'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre la orden'
    )
    
    # ✅ Firmas múltiples de técnicos
    technician_signature_ids = fields.One2many(
        'maintenance.order.technician.signature',
        'order_id',
        string='Firmas de Técnicos',
        help='Firmas de todos los técnicos asignados a esta orden'
    )
    
    # Campos legacy para compatibilidad (se mantienen por ahora)
    technician_signature = fields.Binary(
        string='Firma del Técnico (Temporal)',
        help='Firma digital del técnico que se aplicará a todos los mantenimientos de esta orden',
        attachment=False
    )
    
    technician_signed_by = fields.Many2one(
        'res.users',
        string='Firmado por Técnico',
        readonly=True,
        help='Usuario técnico que firmó la orden'
    )
    
    technician_signed_date = fields.Datetime(
        string='Fecha Firma Técnico',
        readonly=True,
        help='Fecha y hora en que el técnico firmó'
    )
    
    customer_signature = fields.Binary(
        string='Firma del Cliente',
        help='Firma digital del cliente que se aplicará a todos los mantenimientos de esta orden',
        attachment=False
    )
    
    customer_signed_by = fields.Many2one(
        'res.partner',
        string='Firmado por Cliente',
        readonly=True,
        help='Cliente que firmó la orden'
    )
    
    customer_signed_date = fields.Datetime(
        string='Fecha Firma Cliente',
        readonly=True,
        help='Fecha y hora en que el cliente firmó'
    )
    
    is_signed = fields.Boolean(
        string='Está Firmado',
        compute='_compute_is_signed',
        help='Indica si la orden tiene ambas firmas (técnico y cliente)'
    )
    
    # ✅ Campo para el ticket automático
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        readonly=True,
        tracking=True,
        help='Ticket creado automáticamente para esta orden de mantenimiento'
    )
    
    # ========== CAMPOS PARA VISITAS PROGRAMADAS ==========
    
    activity_type = fields.Selection(
        [
            ('maintenance', 'Mantenimiento'),
            ('visit', 'Visita Programada'),
            ('inspection', 'Inspección'),
            ('repair', 'Reparación'),
            ('installation', 'Instalación'),
        ],
        string='Tipo de Actividad',
        default='maintenance',
        required=True,
        tracking=True,
        help='Tipo de actividad técnica a realizar'
    )
    
    visit_purpose = fields.Text(
        string='Propósito de la Visita',
        help='Descripción del objetivo de la visita (visible solo para visitas)'
    )
    
    calendar_event_ids = fields.Many2many(
        'calendar.event',
        'maintenance_order_calendar_event_rel',
        'order_id',
        'event_id',
        string='Eventos de Calendario',
        readonly=True,
        help='Eventos de calendario asociados a esta orden'
    )
    
    is_visit = fields.Boolean(
        string='Es Visita',
        compute='_compute_is_visit',
        store=True,
        help='Indica si es una visita programada'
    )
    
    @api.depends('activity_type')
    def _compute_is_visit(self):
        """Calcular si es una visita programada."""
        for record in self:
            record.is_visit = record.activity_type == 'visit'
    
    @api.depends('maintenance_ids', 'maintenance_ids.status')
    def _compute_maintenance_count(self):
        """Calcular cantidad total y completada de mantenimientos."""
        for order in self:
            order.maintenance_count = len(order.maintenance_ids)
            order.completed_maintenance_count = len(
                order.maintenance_ids.filtered(lambda m: m.status == 'completed')
            )
    
    @api.depends('technician_signature_ids', 'technician_ids', 'customer_signature')
    def _compute_is_signed(self):
        """Calcular si la orden está completamente firmada (todos los técnicos y el cliente)."""
        for order in self:
            # Verificar que todos los técnicos asignados hayan firmado
            signed_technician_ids = order.technician_signature_ids.mapped('technician_id').ids
            all_technicians_signed = (
                len(order.technician_ids) > 0 and 
                len(order.technician_ids) == len(order.technician_signature_ids) and
                all(tech.id in signed_technician_ids for tech in order.technician_ids)
            )
            # Verificar que el cliente haya firmado
            customer_signed = bool(order.customer_signature)
            order.is_signed = all_technicians_signed and customer_signed
    
    def action_add_technician_signature(self):
        """Agregar firma del técnico actual a la lista de firmas."""
        self.ensure_one()
        if not self.technician_signature:
            raise UserError(_('Debe proporcionar una firma primero.'))
        
        # Verificar si el técnico actual ya firmó
        existing_signature = self.technician_signature_ids.filtered(
            lambda s: s.technician_id.id == self.env.user.id
        )
        
        if existing_signature:
            # Actualizar la firma existente
            existing_signature.write({
                'signature': self.technician_signature,
                'signature_date': fields.Datetime.now(),
            })
        else:
            # Crear nueva firma
            self.env['maintenance.order.technician.signature'].create({
                'order_id': self.id,
                'technician_id': self.env.user.id,
                'signature': self.technician_signature,
                'signature_date': fields.Datetime.now(),
            })
        
        # Limpiar el campo temporal
        self.technician_signature = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Firma Agregada'),
                'message': _('Tu firma ha sido agregada a la orden.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.onchange('technician_signature')
    def _onchange_technician_signature(self):
        """Cuando se carga una firma del técnico, preparar para agregarla."""
        # Este método ya no hace nada automático, se usa action_add_technician_signature
        pass
    
    @api.onchange('customer_signature')
    def _onchange_customer_signature(self):
        """Cuando se carga una firma del cliente, guardar cliente y fecha automáticamente."""
        if self.customer_signature:
            if not self.customer_signed_by:
                # Usar el cliente de la orden
                if self.partner_id:
                    self.customer_signed_by = self.partner_id.id
            if not self.customer_signed_date:
                self.customer_signed_date = fields.Datetime.now()
            # La propagación se hace automáticamente en write() cuando se guarda
    
    def _propagate_signatures_to_maintenances(self):
        """Propagar las firmas de la orden a todos los mantenimientos relacionados."""
        if not self.maintenance_ids:
            return
        
        # Preparar valores para actualizar
        update_vals = {}
        if self.technician_signature:
            update_vals['technician_signature'] = self.technician_signature
            if self.technician_signed_by:
                update_vals['technician_signed_by'] = self.technician_signed_by.id
            if self.technician_signed_date:
                update_vals['technician_signed_date'] = self.technician_signed_date
        
        if self.customer_signature:
            update_vals['customer_signature'] = self.customer_signature
            if self.customer_signed_by:
                update_vals['customer_signed_by'] = self.customer_signed_by.id
            if self.customer_signed_date:
                update_vals['customer_signed_date'] = self.customer_signed_date
        
        if update_vals:
            # Actualizar todos los mantenimientos con contexto para evitar validaciones
            self.maintenance_ids.with_context(
                skip_signature_check=True,
                skip_status_validation=True
            ).write(update_vals)
    
    @api.model
    def create(self, vals):
        """Generar número de orden automáticamente y crear ticket."""
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.order') or _('Nuevo')
        order = super().create(vals)
        
        # ✅ Crear ticket automáticamente
        order._create_automatic_ticket()
        
        # Asegurar que existan registros de firma para cada técnico asignado
        if order.technician_ids:
            order._ensure_signature_records_for_technicians()
        
        # Si hay firmas al crear, propagarlas después de crear
        if order.technician_signature or order.customer_signature:
            order._propagate_signatures_to_maintenances()
        
        # ✅ Crear eventos de calendario y recordatorios si está programada
        if order.scheduled_date and order.state in ('scheduled', 'in_progress'):
            order._create_calendar_events()
            order._schedule_reminder_activities()
        
        return order
    
    def write(self, vals):
        """Sobrescribir write para propagar firmas y actualizar ticket."""
        # Verificar si se están guardando firmas
        signatures_changed = 'technician_signature' in vals or 'customer_signature' in vals
        
        result = super().write(vals)
        
        # Si se modificaron los técnicos después de escribir, asegurar que existan registros de firma para cada uno
        if 'technician_ids' in vals:
            for order in self:
                order._ensure_signature_records_for_technicians()
        
        # Si se cambiaron firmas, propagarlas a los mantenimientos
        if signatures_changed:
            for order in self:
                order._propagate_signatures_to_maintenances()
        
        # ✅ Si se modificó el estado, actualizar el ticket (pero no si ya se procesó en action_complete)
        # Verificar si viene del contexto de action_complete
        if 'state' in vals:
            skip_ticket_update = self.env.context.get('skip_ticket_update_on_complete', False)
            if vals['state'] == 'completed' and skip_ticket_update:
                # Ya se procesó en action_complete, no hacer nada más
                pass
            else:
                for order in self:
                    order._update_ticket_status()
            
            # ✅ Actualizar calendario según el estado
            for order in self:
                if vals['state'] == 'cancelled':
                    order._cancel_calendar_events()
                elif vals['state'] in ('scheduled', 'in_progress') and order.scheduled_date:
                    order._create_calendar_events()
                    order._schedule_reminder_activities()
        
        # ✅ Actualizar calendario si cambió fecha programada o técnicos
        calendar_fields = ['scheduled_date', 'deadline_date', 'technician_ids', 'activity_type', 'visit_purpose']
        if any(field in vals for field in calendar_fields):
            for order in self:
                if order.state not in ('cancelled', 'completed'):
                    if order.scheduled_date and order.technician_ids:
                        order._update_calendar_events()
                        if 'scheduled_date' in vals:
                            order._schedule_reminder_activities()
                    elif order.calendar_event_ids:
                        # Si se quitó fecha o técnicos, eliminar eventos
                        order._cancel_calendar_events()
        
        # ✅ Si se modificaron mantenimientos (equipos), actualizar el ticket
        # Esto se manejará desde el wizard cuando se agreguen equipos
        
        return result
    
    def _ensure_signature_records_for_technicians(self):
        """Asegurar que exista un registro de firma para cada técnico asignado."""
        self.ensure_one()
        if not self.technician_ids:
            return
        
        # Obtener IDs de técnicos que ya tienen registro de firma
        existing_signature_tech_ids = self.technician_signature_ids.mapped('technician_id').ids
        
        # Crear registros de firma para técnicos que aún no tienen
        for tech in self.technician_ids:
            if tech.id not in existing_signature_tech_ids:
                self.env['maintenance.order.technician.signature'].create({
                    'order_id': self.id,
                    'technician_id': tech.id,
                    'signature': False,
                })
    
    def action_apply_signatures_to_maintenances(self):
        """Método manual para aplicar las firmas de la orden a todos los mantenimientos."""
        self.ensure_one()
        if not self.maintenance_ids:
            raise UserError(_('No hay mantenimientos en esta orden para aplicar las firmas.'))
        
        self._propagate_signatures_to_maintenances()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Firmas Aplicadas'),
                'message': _('Las firmas se han aplicado a %d mantenimiento(s).') % len(self.maintenance_ids),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_confirm(self):
        """Confirmar la orden y cambiar estado a Programada."""
        for order in self:
            # ✅ Permitir confirmar sin equipos - los técnicos pueden agregar equipos después
            # if not order.maintenance_ids:
            #     raise UserError(_('No se puede confirmar una orden sin mantenimientos.'))
            order.state = 'scheduled'
            # Cambiar estado de los mantenimientos a 'scheduled' si están en 'draft'
            # Usar contexto para saltar la validación de cambio manual de estado
            order.maintenance_ids.filtered(lambda m: m.status == 'draft').with_context(
                skip_status_validation=True
            ).write({'status': 'scheduled'})
            # ✅ Actualizar ticket con el cambio de estado
            order._update_ticket_status()
            # ✅ Crear eventos de calendario y recordatorios
            if order.scheduled_date and order.technician_ids:
                order._create_calendar_events()
                order._schedule_reminder_activities()
    
    def action_start(self):
        """Iniciar la orden y cambiar estado a En Progreso."""
        for order in self:
            order.state = 'in_progress'
            # Cambiar estado de los mantenimientos a 'in_progress' si están en 'scheduled'
            # Usar contexto para saltar la validación de cambio manual de estado
            order.maintenance_ids.filtered(lambda m: m.status == 'scheduled').with_context(
                skip_status_validation=True
            ).write({'status': 'in_progress'})
            # ✅ Actualizar ticket con el cambio de estado
            order._update_ticket_status()
    
    def action_complete(self):
        """Completar la orden, cerrar el ticket y adjuntar el reporte."""
        for order in self:
            # Verificar que todos los mantenimientos estén completados
            incomplete = order.maintenance_ids.filtered(lambda m: m.status != 'completed')
            if incomplete:
                raise UserError(_('No se puede completar la orden. Hay %d mantenimiento(s) sin completar.') % len(incomplete))
            
            # ✅ Actualizar ticket con todos los detalles, cerrarlo y adjuntar reporte ANTES de cambiar el estado
            if order.ticket_id:
                order._complete_ticket_with_details()
            
            # Cambiar el estado después de procesar el ticket (con contexto para evitar doble procesamiento)
            order.with_context(skip_ticket_update_on_complete=True).state = 'completed'
    
    def action_cancel(self):
        """Cancelar la orden."""
        for order in self:
            order.state = 'cancelled'
            # Cancelar mantenimientos pendientes
            order.maintenance_ids.filtered(lambda m: m.status in ('draft', 'scheduled', 'in_progress')).write({'status': 'cancelled'})
            # Cancelar el ticket asociado
            if order.ticket_id:
                order._cancel_ticket()
            # ✅ Cancelar eventos de calendario
            order._cancel_calendar_events()
    
    def action_view_maintenances(self):
        """Abrir vista de mantenimientos de esta orden."""
        self.ensure_one()
        return {
            'name': _('Mantenimientos de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot.maintenance',
            'view_mode': 'list,form',
            'domain': [('maintenance_order_id', '=', self.id)],
            'context': {
                'default_maintenance_order_id': self.id,
                'default_lot_id': False,
            },
        }
    
    def action_add_equipment(self):
        """Abrir wizard para agregar más equipos a la orden."""
        self.ensure_one()
        return {
            'name': _('Agregar Equipos a %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'add.equipment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_maintenance_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
    
    def action_view_ticket(self):
        """Ver el ticket asociado a esta orden."""
        self.ensure_one()
        if not self.ticket_id:
            raise UserError(_('Esta orden no tiene un ticket asociado.'))
        return {
            'name': _('Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_generate_pdf_report(self):
        """Generar reporte PDF de la orden completa con todos los equipos."""
        self.ensure_one()
        if not self.maintenance_ids:
            raise UserError(_('No se puede generar el reporte. Esta orden no tiene equipos asociados.'))
        return self.env.ref('mesa_ayuda_inventario.action_report_maintenance_order').report_action(self)
    
    def _create_automatic_ticket(self):
        """Crear ticket automáticamente para esta orden de mantenimiento."""
        self.ensure_one()
        if self.ticket_id:
            return self.ticket_id
        
        if not self.partner_id:
            # No crear ticket si no hay cliente
            return False
        
        # Preparar nombre del ticket según tipo de actividad
        activity_type_label = dict(self._fields['activity_type'].selection).get(
            self.activity_type, 
            self.activity_type
        )
        ticket_name = _('Orden de Mantenimiento: %s (%s)') % (self.name, activity_type_label)
        
        # Preparar descripción del ticket con formato HTML organizado
        tech_names = ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else _('No asignados')
        scheduled_date_str = self.scheduled_date.strftime('%d/%m/%Y %H:%M') if self.scheduled_date else _('No programada')
        
        ticket_description = f'''
<div style="padding: 15px; background-color: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 4px; margin-bottom: 15px;">
<h3 style="color: #1976d2; margin-top: 0;">📋 Información de la Orden de Mantenimiento</h3>
<div style="line-height: 1.8;">
<p style="margin: 5px 0;"><strong>Orden:</strong> {self.name}</p>
<p style="margin: 5px 0;"><strong>Cliente:</strong> {self.partner_id.name or _("N/A")}</p>
<p style="margin: 5px 0;"><strong>Fecha Programada:</strong> {scheduled_date_str}</p>
<p style="margin: 5px 0;"><strong>Técnicos Asignados:</strong> {tech_names}</p>
</div>
</div>
'''
        
        # Agregar descripción adicional si existe
        if self.description:
            ticket_description += f'<div style="margin-top: 15px;"><p><strong>Descripción:</strong></p><p>{self.description}</p></div>'
        
        # Crear el ticket
        ticket = self.env['helpdesk.ticket'].create({
            'name': ticket_name,
            'partner_id': self.partner_id.id,
            'description': ticket_description,
            'maintenance_order_id': self.id,
            'maintenance_category': 'maintenance',
            'user_id': self.technician_ids[0].id if self.technician_ids else self.env.user.id,
        })
        
        # Vincular el ticket a la orden
        self.ticket_id = ticket.id
        
        # Notificar en el chatter
        self.message_post(
            body=_('Ticket creado automáticamente: %s') % ticket.name,
            subject=_('Ticket Creado')
        )
        
        return ticket
    
    def _update_ticket_with_equipment(self):
        """Actualizar el ticket con información de los equipos agregados."""
        self.ensure_one()
        if not self.ticket_id:
            return
        
        # Crear tabla HTML organizada de equipos
        equipment_rows = []
        for maintenance in self.maintenance_ids:
            if maintenance.lot_id:
                # Equipo de la empresa (stock.lot)
                plate = maintenance.lot_id.inventory_plate or _('Sin placa')
                serial = maintenance.lot_id.name or _('N/A')
                product = maintenance.lot_id.product_id.name if maintenance.lot_id.product_id else _('N/A')
                equipment_type = _('Empresa')
                
                equipment_rows.append(f'<tr><td>{serial}</td><td>{plate}</td><td>{product}</td><td>{equipment_type}</td></tr>')
            elif maintenance.own_inventory_id:
                # Equipo propio del cliente (customer.own.inventory)
                serial = maintenance.own_inventory_id.serial_number or _('N/A')
                product = maintenance.own_inventory_id.product_id.name if maintenance.own_inventory_id.product_id else _('N/A')
                plate = _('N/A')
                equipment_type = _('Propio del Cliente')
                
                equipment_rows.append(f'<tr><td>{serial}</td><td>{plate}</td><td>{product}</td><td>{equipment_type}</td></tr>')
        
        if equipment_rows:
            equipment_section = f'''
<div style="margin-top: 20px; margin-bottom: 20px;">
<h3 style="color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 5px;">📋 Equipos en esta Orden ({len(equipment_rows)} equipo(s))</h3>
<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
<thead>
<tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
<th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Número de Serie</th>
<th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Placa de Inventario</th>
<th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Producto</th>
<th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Tipo</th>
</tr>
</thead>
<tbody>
{''.join(equipment_rows)}
</tbody>
</table>
</div>
'''
            
            # Actualizar descripción manteniendo la información original
            current_description = self.ticket_id.description or ''
            # Eliminar la sección de equipos anterior si existe (tanto texto como HTML)
            import re as re_module
            # Eliminar sección HTML de equipos
            current_description = re_module.sub(r'<div[^>]*>.*?Equipos en esta Orden.*?</div>', '', current_description, flags=re_module.DOTALL)
            # Eliminar sección de texto de equipos
            if '--- Equipos en esta orden ---' in current_description:
                parts = current_description.split('--- Equipos en esta orden ---')
                current_description = parts[0].strip()
            
            # Combinar descripción original con nueva sección de equipos
            if current_description:
                self.ticket_id.description = current_description + equipment_section
            else:
                self.ticket_id.description = equipment_section
            
            # Notificar en el chatter del ticket
            self.ticket_id.message_post(
                body=_('Equipos actualizados en la orden de mantenimiento %s. Total: %d equipo(s).') % (
                    self.name,
                    len(equipment_rows)
                ),
                subject=_('Actualización de Equipos')
            )
    
    def _update_ticket_status(self):
        """Actualizar el estado del ticket según el estado de la orden."""
        self.ensure_one()
        if not self.ticket_id:
            return
        
        # Obtener la etiqueta del estado actual
        status_label = dict(self._fields['state'].selection).get(self.state, self.state)
        
        # Notificar en el chatter del ticket sobre el cambio de estado
        try:
            self.ticket_id.message_post(
                body=_('Estado de la orden de mantenimiento %s actualizado a: %s') % (
                    self.name,
                    status_label
                ),
                subject=_('Actualización de Estado')
            )
        except Exception as e:
            _logger.warning("No se pudo actualizar el mensaje del ticket: %s", str(e))
        
        # Intentar actualizar el stage del ticket si existe el modelo y el campo
        # Envolver todo en try-except para que no falle si el modelo no existe
        try:
            if hasattr(self.ticket_id, 'stage_id'):
                # Mapeo de estados de orden a nombres de stages comunes
                stage_name_mapping = {
                    'draft': 'Nuevo',
                    'scheduled': 'En Progreso',
                    'in_progress': 'En Progreso',
                    'completed': 'Cerrado',
                    'cancelled': 'Cancelado',
                }
                
                stage_name = stage_name_mapping.get(self.state)
                if stage_name:
                    # Intentar buscar stage - puede fallar si el modelo no existe
                    # Envolver la búsqueda del modelo en try-except
                    try:
                        stages = self.env['helpdesk.ticket.stage'].search([
                            ('name', 'ilike', stage_name)
                        ], limit=1)
                        if stages:
                            self.ticket_id.stage_id = stages[0].id
                    except KeyError:
                        # El modelo no existe, simplemente ignorar
                        pass
        except Exception as e:
            # Si hay cualquier otro error, solo loguearlo pero no fallar
            _logger.debug("No se pudo actualizar el stage del ticket: %s", str(e))
    
    def _cancel_ticket(self):
        """Cancelar el ticket asociado cuando se cancela la orden de mantenimiento."""
        self.ensure_one()
        if not self.ticket_id:
            _logger.warning("La orden %s no tiene ticket asociado para cancelar", self.name)
            return
        
        _logger.info("Iniciando proceso de cancelar ticket %s para la orden %s", self.ticket_id.name, self.name)
        
        try:
            # Actualizar la descripción del ticket con información de cancelación
            cancellation_message = _('=== ORDEN DE MANTENIMIENTO CANCELADA ===\n')
            cancellation_message += _('Orden de Mantenimiento: %s\n') % self.name
            cancellation_message += _('Cliente: %s\n') % (self.partner_id.name or 'N/A')
            cancellation_message += _('Fecha de Cancelación: %s\n') % fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            cancellation_message += _('\nEsta orden de mantenimiento ha sido cancelada.')
            
            # Actualizar descripción del ticket
            new_description = (self.ticket_id.description or '') + '\n\n' + cancellation_message
            self.ticket_id.description = new_description
            
            # Buscar stage "Cancelado" y mover el ticket a ese stage
            ticket_cancelled = False
            try:
                if hasattr(self.ticket_id, 'stage_id') and self.ticket_id.stage_id:
                    stage_model = self.ticket_id.stage_id._name
                    _logger.info("🔍 Buscando stage de Cancelado para ticket %s", self.ticket_id.name)
                    
                    try:
                        # Buscar todos los stages disponibles
                        all_stages = self.env[stage_model].search([], order='sequence')
                        
                        # Estrategia 1: Buscar por nombre "Cancelado"
                        stage_names_to_search = ['Cancelado', 'Cancel', 'Cancelad', 'Anulado', 'Anular', 'Cancelled']
                        
                        for stage_name in stage_names_to_search:
                            try:
                                cancelled_stages = self.env[stage_model].search([
                                    ('name', 'ilike', stage_name)
                                ], limit=1)
                                
                                if cancelled_stages:
                                    self.ticket_id.sudo().write({'stage_id': cancelled_stages[0].id})
                                    self.ticket_id.invalidate_recordset(['stage_id'])
                                    ticket_cancelled = True
                                    _logger.info("✅ Ticket %s cancelado usando stage '%s': %s", self.ticket_id.name, stage_name, cancelled_stages[0].name)
                                    break
                            except Exception as search_error:
                                _logger.debug("Error al buscar stage '%s': %s", stage_name, str(search_error))
                        
                        # Estrategia 2: Si no se encuentra, usar un stage intermedio o el último
                        if not ticket_cancelled and all_stages:
                            # Intentar usar un stage que no sea "Nuevo" o "En Progreso"
                            intermediate_stages = all_stages.filtered(
                                lambda s: s.name.lower() not in ['nuevo', 'new', 'en progreso', 'in progress', 'en proceso']
                            )
                            if intermediate_stages:
                                target_stage = intermediate_stages[0]
                            else:
                                target_stage = all_stages[-1]  # Último stage
                            
                            try:
                                self.ticket_id.sudo().write({'stage_id': target_stage.id})
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_cancelled = True
                                _logger.info("✅ Ticket %s movido a stage intermedio: %s", self.ticket_id.name, target_stage.name)
                            except Exception as stage_error:
                                _logger.error("❌ Error al mover ticket a stage: %s. Traceback: %s", str(stage_error), traceback.format_exc())
                    except Exception as model_error:
                        _logger.error("❌ Error al acceder al modelo '%s': %s. Traceback: %s", stage_model, str(model_error), traceback.format_exc())
                else:
                    _logger.warning("⚠️ El ticket no tiene campo stage_id o no tiene un stage asignado")
                    
            except Exception as e:
                _logger.error("❌ Error al cancelar el ticket automáticamente: %s. Traceback: %s", str(e), traceback.format_exc())
            
            # Notificar en el chatter del ticket
            status_message = _('La orden de mantenimiento %s ha sido cancelada.') % self.name
            if not ticket_cancelled:
                status_message += _(' ⚠️ El ticket no se pudo cancelar automáticamente, por favor cancelarlo manualmente.')
            
            self.ticket_id.message_post(
                body=status_message,
                subject=_('Orden Cancelada')
            )
            
            _logger.info("✅ Proceso de cancelar ticket finalizado para la orden %s. Ticket cancelado: %s", self.name, ticket_cancelled)
            
        except Exception as e:
            _logger.error("❌ Error al cancelar el ticket: %s. Traceback: %s", str(e), traceback.format_exc())
    
    def _complete_ticket_with_details(self):
        """Completar el ticket: agregar detalles de mantenimientos, cerrarlo y adjuntar reporte PDF."""
        self.ensure_one()
        if not self.ticket_id:
            _logger.warning("La orden %s no tiene ticket asociado", self.name)
            return
        
        _logger.info("Iniciando proceso de completar ticket %s para la orden %s", self.ticket_id.name, self.name)
        
        try:
            # 1. Crear resumen organizado con HTML formateado
            # Información general de la orden
            tech_names = ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else _('N/A')
            scheduled_date_str = self.scheduled_date.strftime('%d/%m/%Y %H:%M:%S') if self.scheduled_date else _('N/A')
            
            summary_header = f'''
<div style="margin-top: 20px; margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #28a745; border-radius: 4px;">
<h2 style="color: #28a745; margin-top: 0; margin-bottom: 15px;">✅ RESUMEN DE MANTENIMIENTOS COMPLETADOS</h2>
<div style="line-height: 1.8;">
<p style="margin: 5px 0;"><strong>Orden de Mantenimiento:</strong> {self.name}</p>
<p style="margin: 5px 0;"><strong>Cliente:</strong> {self.partner_id.name or _("N/A")}</p>
<p style="margin: 5px 0;"><strong>Fecha Programada:</strong> {scheduled_date_str}</p>
<p style="margin: 5px 0;"><strong>Técnicos Asignados:</strong> {tech_names}</p>
<p style="margin: 5px 0;"><strong>Total de Equipos:</strong> {len(self.maintenance_ids)} equipo(s)</p>
</div>
</div>
'''
            
            # Crear tabla compacta de equipos mantenidos
            equipment_rows = []
            for idx, maintenance in enumerate(self.maintenance_ids, 1):
                if maintenance.lot_id:
                    # Equipo de la empresa
                    plate = maintenance.inventory_plate or _('Sin placa')
                    serial = maintenance.lot_id.name or _('N/A')
                    product = maintenance.lot_id.product_id.name if maintenance.lot_id.product_id else _('N/A')
                elif maintenance.own_inventory_id:
                    # Equipo propio del cliente
                    plate = _('N/A')
                    serial = maintenance.own_inventory_id.serial_number or _('N/A')
                    product = maintenance.own_inventory_id.product_id.name if maintenance.own_inventory_id.product_id else _('N/A')
                else:
                    plate = _('N/A')
                    serial = _('N/A')
                    product = _('N/A')
                
                type_label = _('N/A')
                if maintenance.maintenance_type:
                    type_label = dict(maintenance._fields['maintenance_type'].selection).get(maintenance.maintenance_type, maintenance.maintenance_type)
                
                date_str = maintenance.maintenance_date.strftime('%d/%m/%Y %H:%M') if maintenance.maintenance_date else _('N/A')
                
                maint_techs = ', '.join(maintenance.technician_ids.mapped('name')) if maintenance.technician_ids else _('N/A')
                
                # Limpiar descripción si existe
                description_text = ''
                if maintenance.description:
                    clean_description = re.sub('<[^<]+?>', '', maintenance.description)
                    clean_description = clean_description.replace('&nbsp;', ' ').strip()
                    if clean_description:
                        description_text = clean_description[:150] + ('...' if len(clean_description) > 150 else '')
                
                equipment_rows.append(f'''
<tr style="border-bottom: 1px solid #dee2e6;">
<td style="padding: 10px; text-align: center; font-weight: bold;">{idx}</td>
<td style="padding: 10px;">{serial}<br/><small style="color: #6c757d;">Placa: {plate}</small></td>
<td style="padding: 10px;">{product}</td>
<td style="padding: 10px;">{type_label}</td>
<td style="padding: 10px;">{date_str}<br/><small style="color: #6c757d;">{maint_techs}</small></td>
<td style="padding: 10px;"><small style="color: #6c757d;">{description_text or _("Sin descripción")}</small></td>
</tr>
''')
            
            equipment_table = f'''
<div style="margin-top: 20px; margin-bottom: 20px;">
<h3 style="color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 5px;">📋 Equipos Mantenidos ({len(equipment_rows)} equipo(s))</h3>
<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
<thead>
<tr style="background-color: #667eea; color: white;">
<th style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">#</th>
<th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Serie / Placa</th>
<th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Producto</th>
<th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Tipo de Servicio</th>
<th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Fecha / Técnicos</th>
<th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Descripción</th>
</tr>
</thead>
<tbody>
{''.join(equipment_rows)}
</tbody>
</table>
</div>
'''
            
            # Combinar todo
            summary_section = summary_header + equipment_table
            
            # Obtener descripción actual y limpiar resúmenes anteriores si existen
            current_description = self.ticket_id.description or ''
            # Eliminar resúmenes anteriores (tanto HTML como texto plano)
            import re as re_module
            # Eliminar sección HTML de resumen
            current_description = re_module.sub(r'<div[^>]*>.*?RESUMEN DE MANTENIMIENTOS COMPLETADOS.*?</div>', '', current_description, flags=re_module.DOTALL)
            current_description = re_module.sub(r'<div[^>]*>.*?Equipos Mantenidos.*?</div>', '', current_description, flags=re_module.DOTALL)
            # Eliminar sección de texto plano
            if '=== RESUMEN DE MANTENIMIENTOS COMPLETADOS ===' in current_description:
                parts = current_description.split('=== RESUMEN DE MANTENIMIENTOS COMPLETADOS ===')
                current_description = parts[0].strip()
            
            # Actualizar descripción del ticket
            if current_description:
                self.ticket_id.description = current_description + summary_section
            else:
                self.ticket_id.description = summary_section
            
            # 2. Cerrar el ticket (buscar stage "Cerrado" o "Resuelto")
            ticket_closed = False
            try:
                if hasattr(self.ticket_id, 'stage_id') and self.ticket_id.stage_id:
                    # Acceder al modelo de stages a través del campo stage_id del ticket
                    stage_model = self.ticket_id.stage_id._name
                    _logger.info("🔍 Modelo de stage encontrado a través del ticket: %s", stage_model)
                    
                    try:
                        # Buscar todos los stages disponibles primero para debug
                        all_stages = self.env[stage_model].search([], order='sequence')
                        stage_names = all_stages.mapped('name')
                        _logger.info("🔍 Stages disponibles en el sistema (%d): %s", len(all_stages), ', '.join(stage_names))
                        
                        # Estrategia 1: Buscar por campo 'closed' si existe
                        try:
                            closed_stage = self.env[stage_model].search([
                                ('closed', '=', True)
                            ], limit=1, order='sequence desc')
                            
                            if closed_stage:
                                self.ticket_id.sudo().write({'stage_id': closed_stage[0].id})
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_closed = True
                                _logger.info("✅ Ticket %s cerrado usando stage con closed=True: %s", self.ticket_id.name, closed_stage[0].name)
                        except Exception as e:
                            _logger.debug("Campo 'closed' no existe en stages: %s", str(e))
                        
                        # Estrategia 2: Buscar por nombre (variaciones comunes)
                        if not ticket_closed:
                            stage_names_to_search = ['Resuelto', 'Cerrado', 'Cerr', 'Resuel', 'Finalizado', 'Completado', 'Done', 'Solved']
                            
                            for stage_name in stage_names_to_search:
                                try:
                                    closed_stages_by_name = self.env[stage_model].search([
                                        ('name', 'ilike', stage_name)
                                    ], limit=1)
                                    
                                    if closed_stages_by_name:
                                        self.ticket_id.sudo().write({'stage_id': closed_stages_by_name[0].id})
                                        self.ticket_id.invalidate_recordset(['stage_id'])
                                        ticket_closed = True
                                        _logger.info("✅ Ticket %s cerrado usando stage por nombre '%s': %s", self.ticket_id.name, stage_name, closed_stages_by_name[0].name)
                                        break
                                except Exception as search_error:
                                    _logger.debug("Error al buscar stage '%s': %s", stage_name, str(search_error))
                        
                        # Estrategia 3: Si no se encuentra, usar el último stage por sequence
                        if not ticket_closed and all_stages:
                            last_stage = all_stages[-1]  # El último por sequence
                            try:
                                self.ticket_id.sudo().write({'stage_id': last_stage.id})
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_closed = True
                                _logger.info("✅ Ticket %s movido al último stage disponible: %s (ID: %s)", self.ticket_id.name, last_stage.name, last_stage.id)
                            except Exception as stage_error:
                                _logger.error("❌ Error al mover ticket al último stage: %s. Traceback: %s", str(stage_error), traceback.format_exc())
                    except Exception as model_error:
                        _logger.error("❌ Error al acceder al modelo '%s': %s. Traceback: %s", stage_model, str(model_error), traceback.format_exc())
                else:
                    _logger.warning("⚠️ El ticket no tiene campo stage_id o no tiene un stage asignado")
                    
            except Exception as e:
                _logger.error("❌ Error al cerrar el ticket automáticamente: %s. Traceback: %s", str(e), traceback.format_exc())
            
            if not ticket_closed:
                _logger.warning("⚠️ El ticket %s NO se cerró automáticamente. Por favor cerrarlo manualmente.", self.ticket_id.name)
            
            # 3. Generar y adjuntar el reporte PDF
            pdf_attached = False
            try:
                report_action = self.env.ref('mesa_ayuda_inventario.action_report_maintenance_order', raise_if_not_found=False)
                if not report_action:
                    _logger.warning("⚠️ No se encontró la acción del reporte: mesa_ayuda_inventario.action_report_maintenance_order")
                else:
                    _logger.info("📄 Generando PDF para la orden %s (ID: %s)", self.name, self.id)
                    
                    # Intentar generar el PDF
                    try:
                        # Usar el método correcto para renderizar el PDF
                        # Obtener el report_ref desde el report_name del reporte
                        report_ref = report_action.report_name or 'mesa_ayuda_inventario.report_maintenance_order'
                        _logger.info("📄 Intentando generar PDF con report_ref: %s para orden ID: %s", report_ref, self.id)
                        
                        # Llamar al método con los parámetros correctos
                        pdf_content, dummy_report_format = report_action._render_qweb_pdf(report_ref, res_ids=[self.id], data=None)
                        _logger.info("📄 PDF generado para la orden %s. Tamaño: %s bytes", self.name, len(pdf_content) if pdf_content else 0)
                    except Exception as render_error:
                        _logger.error("❌ Error al renderizar PDF: %s. Traceback: %s", str(render_error), traceback.format_exc())
                        pdf_content = None
                    
                    if not pdf_content:
                        _logger.warning("⚠️ El reporte PDF está vacío o no se generó para la orden %s", self.name)
                    else:
                        # Crear adjunto del reporte
                        attachment_name = 'Reporte_Orden_Mantenimiento_%s.pdf' % self.name.replace('/', '_')
                        
                        # Asegurar que pdf_content sea bytes
                        if isinstance(pdf_content, str):
                            pdf_content = pdf_content.encode('utf-8')
                        elif not isinstance(pdf_content, bytes):
                            try:
                                pdf_content = bytes(pdf_content)
                            except:
                                pdf_content = str(pdf_content).encode('utf-8')
                        
                        try:
                            attachment = self.env['ir.attachment'].sudo().create({
                                'name': attachment_name,
                                'type': 'binary',
                                'datas': base64.b64encode(pdf_content).decode('ascii'),
                                'res_model': 'helpdesk.ticket',
                                'res_id': self.ticket_id.id,
                                'mimetype': 'application/pdf',
                            })
                            
                            pdf_attached = True
                            _logger.info("✅ PDF adjuntado al ticket %s (ID: %s): %s", self.ticket_id.name, self.ticket_id.id, attachment_name)
                            
                            # Notificar en el chatter del ticket
                            self.ticket_id.message_post(
                                body=_('✅ Reporte PDF de la orden de mantenimiento adjuntado: %s') % attachment_name,
                                subject=_('Reporte Adjuntado'),
                                attachment_ids=[(6, 0, [attachment.id])]
                            )
                        except Exception as attach_error:
                            _logger.error("❌ Error al crear adjunto: %s. Traceback: %s", str(attach_error), traceback.format_exc())
                            
            except Exception as e:
                _logger.error("❌ Error al generar o adjuntar el reporte PDF al ticket: %s. Traceback: %s", str(e), traceback.format_exc())
            
            if not pdf_attached:
                _logger.warning("⚠️ El reporte PDF NO se adjuntó al ticket %s", self.ticket_id.name)
            
            # 4. Notificar en el chatter del ticket sobre el cierre
            status_message = _('✅ Orden de mantenimiento completada.')
            if ticket_closed:
                status_message += _(' El ticket ha sido cerrado automáticamente.')
            else:
                status_message += _(' ⚠️ El ticket no se pudo cerrar automáticamente, por favor cerrarlo manualmente.')
            
            if pdf_attached:
                status_message += _(' Reporte PDF adjuntado.')
            else:
                status_message += _(' ⚠️ El reporte PDF no se pudo adjuntar.')
            
            self.ticket_id.message_post(
                body=status_message,
                subject=_('Orden Completada')
            )
            
            _logger.info("✅ Proceso de completar ticket finalizado para la orden %s. Ticket cerrado: %s, PDF adjuntado: %s", self.name, ticket_closed, pdf_attached)
            
        except Exception as e:
            _logger.error("❌ Error al completar el ticket con detalles: %s. Traceback: %s", str(e), traceback.format_exc())
    
    # ========== MÉTODOS PARA CALENDARIO Y VISITAS PROGRAMADAS ==========
    
    def _create_calendar_events(self):
        """Crear eventos de calendario para cada técnico asignado."""
        self.ensure_one()
        
        # No crear eventos si no hay fecha programada o técnicos
        if not self.scheduled_date or not self.technician_ids:
            return
        
        # Eliminar eventos existentes primero
        if self.calendar_event_ids:
            self.calendar_event_ids.unlink()
        
        # Obtener tipo de actividad para el título
        activity_type_label = dict(self._fields['activity_type'].selection).get(
            self.activity_type, 
            self.activity_type
        )
        
        # Calcular fecha de fin (usar deadline_date si existe, sino 2 horas después)
        start_date = self.scheduled_date
        if self.deadline_date:
            stop_date = self.deadline_date
        else:
            # Por defecto, 2 horas de duración
            from datetime import timedelta
            if isinstance(start_date, str):
                start_date = fields.Datetime.from_string(start_date)
            stop_date = start_date + timedelta(hours=2)
        
        # Preparar descripción del evento
        description_parts = []
        if self.partner_id:
            description_parts.append(f"Cliente: {self.partner_id.name}")
        if self.visit_purpose:
            description_parts.append(f"Propósito: {self.visit_purpose}")
        elif self.description:
            # Limpiar HTML si existe
            clean_description = re.sub('<[^<]+?>', '', self.description)
            clean_description = clean_description.replace('&nbsp;', ' ').strip()
            if clean_description:
                description_parts.append(f"Descripción: {clean_description[:200]}")
        
        description = '\n'.join(description_parts) if description_parts else ''
        
        # Crear un evento para cada técnico (o un evento compartido)
        # Opción 1: Un evento compartido con todos los técnicos
        event_vals = {
            'name': f"{activity_type_label}: {self.name} - {self.partner_id.name if self.partner_id else 'Sin cliente'}",
            'start': start_date,
            'stop': stop_date,
            'partner_ids': [(6, 0, [self.partner_id.id])] if self.partner_id else [],
            'user_id': self.technician_ids[0].id if self.technician_ids else self.env.user.id,
            'description': description or '',
            'location': self.partner_id.street if self.partner_id and self.partner_id.street else '',
            'categ_ids': [(6, 0, [])],  # Categorías opcionales
        }
        
        # Agregar todos los técnicos como participantes
        attendee_ids = []
        for technician in self.technician_ids:
            attendee_ids.append((0, 0, {
                'partner_id': technician.partner_id.id if technician.partner_id else False,
            }))
        
        if attendee_ids:
            event_vals['attendee_ids'] = attendee_ids
        
        try:
            event = self.env['calendar.event'].create(event_vals)
            self.write({'calendar_event_ids': [(4, event.id)]})
            
            # Notificar en el chatter
            self.message_post(
                body=_('✅ Evento de calendario creado automáticamente para %s') % (
                    ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else 'técnicos asignados'
                ),
                subject=_('Evento de Calendario Creado')
            )
            
            _logger.info("✅ Evento de calendario creado para orden %s: %s", self.name, event.name)
        except Exception as e:
            _logger.error("❌ Error al crear evento de calendario para orden %s: %s. Traceback: %s", 
                         self.name, str(e), traceback.format_exc())
    
    def _update_calendar_events(self):
        """Actualizar eventos de calendario cuando cambian datos."""
        self.ensure_one()
        
        if not self.calendar_event_ids:
            # Si no hay eventos pero hay fecha y técnicos, crear
            if self.scheduled_date and self.technician_ids and self.state != 'cancelled':
                self._create_calendar_events()
            return
        
        # Actualizar eventos existentes
        activity_type_label = dict(self._fields['activity_type'].selection).get(
            self.activity_type, 
            self.activity_type
        )
        
        start_date = self.scheduled_date
        if self.deadline_date:
            stop_date = self.deadline_date
        else:
            from datetime import timedelta
            if isinstance(start_date, str):
                start_date = fields.Datetime.from_string(start_date)
            stop_date = start_date + timedelta(hours=2)
        
        description_parts = []
        if self.partner_id:
            description_parts.append(f"Cliente: {self.partner_id.name}")
        if self.visit_purpose:
            description_parts.append(f"Propósito: {self.visit_purpose}")
        elif self.description:
            clean_description = re.sub('<[^<]+?>', '', self.description)
            clean_description = clean_description.replace('&nbsp;', ' ').strip()
            if clean_description:
                description_parts.append(f"Descripción: {clean_description[:200]}")
        
        description = '\n'.join(description_parts) if description_parts else ''
        
        update_vals = {
            'name': f"{activity_type_label}: {self.name} - {self.partner_id.name if self.partner_id else 'Sin cliente'}",
            'start': start_date,
            'stop': stop_date,
            'description': description or '',
            'location': self.partner_id.street if self.partner_id and self.partner_id.street else '',
        }
        
        try:
            self.calendar_event_ids.write(update_vals)
            _logger.info("✅ Eventos de calendario actualizados para orden %s", self.name)
        except Exception as e:
            _logger.error("❌ Error al actualizar eventos de calendario para orden %s: %s", 
                         self.name, str(e))
    
    def _cancel_calendar_events(self):
        """Cancelar o eliminar eventos de calendario cuando se cancela la orden."""
        self.ensure_one()
        
        if self.calendar_event_ids:
            try:
                # Eliminar los eventos
                self.calendar_event_ids.unlink()
                _logger.info("✅ Eventos de calendario eliminados para orden cancelada %s", self.name)
            except Exception as e:
                _logger.error("❌ Error al eliminar eventos de calendario para orden %s: %s", 
                             self.name, str(e))
    
    def _schedule_reminder_activities(self):
        """Programar actividades de recordatorio antes de la visita/mantenimiento."""
        self.ensure_one()
        
        if not self.scheduled_date or self.state in ('cancelled', 'completed'):
            return
        
        # Eliminar recordatorios existentes de esta orden
        existing_activities = self.activity_ids.filtered(
            lambda a: a.activity_type_id and 'recordatorio' in a.activity_type_id.name.lower()
        )
        if existing_activities:
            existing_activities.unlink()
        
        # Calcular fecha del recordatorio (1 día antes)
        from datetime import timedelta
        if isinstance(self.scheduled_date, str):
            scheduled_dt = fields.Datetime.from_string(self.scheduled_date)
        else:
            scheduled_dt = self.scheduled_date
        
        reminder_date = scheduled_dt - timedelta(days=1)
        
        # Solo crear recordatorio si la fecha programada es en el futuro
        if reminder_date > fields.Datetime.now():
            activity_type_label = dict(self._fields['activity_type'].selection).get(
                self.activity_type, 
                self.activity_type
            )
            
            # Buscar tipo de actividad "Recordatorio" o crear uno genérico
            activity_type = self.env['mail.activity.type'].search([
                ('name', 'ilike', 'Recordatorio')
            ], limit=1)
            
            if not activity_type:
                # Usar un tipo genérico si no existe
                activity_type = self.env['mail.activity.type'].search([
                    ('category', '=', 'reminder')
                ], limit=1)
            
            # Crear actividad de recordatorio para cada técnico
            for technician in self.technician_ids:
                try:
                    self.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        date_deadline=reminder_date.date(),
                        summary=_('Recordatorio: %s programado para %s') % (
                            activity_type_label,
                            scheduled_dt.strftime('%d/%m/%Y %H:%M')
                        ),
                        note=_('Recordatorio de %s\n\nCliente: %s\nFecha: %s\n%s') % (
                            activity_type_label,
                            self.partner_id.name if self.partner_id else 'N/A',
                            scheduled_dt.strftime('%d/%m/%Y %H:%M'),
                            self.visit_purpose if self.visit_purpose else (self.description or '')
                        ),
                        user_id=technician.id
                    )
                except Exception as e:
                    _logger.warning("No se pudo crear actividad de recordatorio para técnico %s: %s", 
                                   technician.name, str(e))
    
    def action_view_calendar(self):
        """Abrir vista de calendario mostrando esta orden."""
        self.ensure_one()
        if not self.calendar_event_ids:
            raise UserError(_('Esta orden no tiene eventos de calendario asociados.'))
        
        return {
            'name': _('Calendario'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,form',
            'domain': [('id', 'in', self.calendar_event_ids.ids)],
            'target': 'current',
        }


class MaintenanceOrderTechnicianSignature(models.Model):
    """Firmas individuales de técnicos en una orden de mantenimiento."""
    _name = 'maintenance.order.technician.signature'
    _description = 'Firma de Técnico en Orden de Mantenimiento'
    _order = 'technician_id'
    
    order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    technician_id = fields.Many2one(
        'res.users',
        string='Técnico',
        required=True,
        help='Técnico que firmó'
    )
    
    signature = fields.Binary(
        string='Firma',
        attachment=False,
        required=False,
        help='Firma digital del técnico'
    )
    
    signature_date = fields.Datetime(
        string='Fecha de Firma',
        default=False,
        required=False,
        readonly=True,
        help='Fecha y hora en que el técnico firmó'
    )
    
    @api.onchange('signature')
    def _onchange_signature(self):
        """Cuando se carga una firma, establecer la fecha automáticamente (similar a customer_signature)."""
        if self.signature:
            if not self.signature_date:
                self.signature_date = fields.Datetime.now()
    
    @api.model
    def create(self, vals):
        """Crear registro de firma."""
        # Si se proporciona una firma, establecer la fecha automáticamente
        if 'signature' in vals and vals.get('signature'):
            # Verificar que la firma tenga contenido válido
            signature_value = vals.get('signature')
            if signature_value not in (False, None, '', b''):
                if not vals.get('signature_date'):
                    vals['signature_date'] = fields.Datetime.now()
        return super().create(vals)
    
    def write(self, vals):
        """Actualizar fecha de firma cuando se guarda una firma (similar a customer_signature)."""
        # Si se está guardando una firma, actualizar la fecha automáticamente
        if 'signature' in vals and vals.get('signature'):
            # Si hay firma, establecer la fecha automáticamente si no existe
            # No verificar el valor en detalle, solo si existe
            if not self.signature_date:
                vals['signature_date'] = fields.Datetime.now()
        result = super().write(vals)
        # Después de guardar, invalidar el caché para refrescar
        if 'signature' in vals:
            self.invalidate_recordset(['signature', 'signature_date'])
        return result

