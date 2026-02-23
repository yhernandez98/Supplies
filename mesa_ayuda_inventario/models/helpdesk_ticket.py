# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    """Extensión del módulo nativo helpdesk.ticket para agregar campos de mantenimiento.
    Prioridad, SLA y orden de servicio se rellenan/crean según la categoría del ticket."""
    _inherit = 'helpdesk.ticket'  # ✅ Extendiendo el modelo nativo

    @api.constrains('user_id')
    def _check_assigned_required(self):
        """El campo Asignada a es obligatorio para poder guardar el ticket."""
        for ticket in self:
            if not ticket.user_id:
                raise UserError(_('El ticket debe tener un responsable asignado (Asignada a).'))
    
    # Campos adicionales para integración con mantenimientos
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        domain="[('customer_id', '=', partner_id)]",
        tracking=True,
        help='Equipo relacionado con el ticket'
    )
    
    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        tracking=True,
        help='Orden de mantenimiento relacionada (creada automáticamente por categoría o manualmente)'
    )
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
        tracking=True,
        help='Mantenimiento relacionado'
    )
    
    category_id = fields.Many2one(
        'helpdesk.ticket.category',
        string='Categoría',
        tracking=True,
    )

    # Tipo GLPI: urgencia e impacto
    urgency = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Urgencia', default='2', tracking=True)
    impact = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Impacto', default='2', tracking=True)
    location_site = fields.Char(string='Ubicación / Sede', tracking=True)
    date_deadline_response = fields.Datetime(string='Compromiso respuesta (SLA)', tracking=True)
    date_deadline_resolution = fields.Datetime(string='Compromiso resolución (SLA)', tracking=True)

    # Si True, prioridad/urgencia/impacto/SLA fueron fijados por la categoría y el técnico no debe editarlos
    values_from_category = fields.Boolean(
        string='Valores fijados por categoría',
        default=False,
        help='Cuando está activo, Prioridad, Urgencia, Impacto y fechas SLA son solo lectura (definidos por la categoría).'
    )

    # Categoría personalizada para distinguir tickets de mantenimiento
    maintenance_category = fields.Selection([
        ('maintenance', 'Mantenimiento'),
        ('repair', 'Reparación'),
        ('support', 'Soporte'),
        ('change', 'Cambio de Equipo'),
        ('other', 'Otro'),
    ], string='Categoría Mantenimiento', tracking=True)

    def _apply_category_defaults(self, category):
        """Devuelve un diccionario de valores a aplicar al ticket según la categoría (prioridad, SLA, urgencia, impacto)."""
        vals = {}
        if not category:
            return vals
        if category.default_priority:
            # helpdesk.ticket.priority en Odoo estándar es string ('0','1','2','3')
            vals['priority'] = category.default_priority
        if category.default_urgency:
            vals['urgency'] = category.default_urgency
        if category.default_impact:
            vals['impact'] = category.default_impact
        now = fields.Datetime.now()
        # Intervalo SLA: días + horas
        resp_days = category.sla_response_days or 0
        resp_hours = category.sla_response_hours or 0
        if resp_days or resp_hours:
            vals['date_deadline_response'] = now + timedelta(days=resp_days, hours=resp_hours)
        res_days = category.sla_resolution_days or 0
        res_hours = category.sla_resolution_hours or 0
        if res_days or res_hours:
            vals['date_deadline_resolution'] = now + timedelta(days=res_days, hours=res_hours)
        if vals:
            vals['values_from_category'] = True
        return vals

    def _create_maintenance_order_from_ticket(self):
        """Crea una orden de mantenimiento enlazada a este ticket (partner, descripción)."""
        self.ensure_one()
        if self.maintenance_order_id:
            return self.maintenance_order_id
        if not self.partner_id:
            return self.env['maintenance.order']
        desc = (self.name or '') + '\n\n' + (self.description or '')
        order_vals = {
            'partner_id': self.partner_id.id,
            'description': desc,
            'ticket_id': self.id,
        }
        if self.user_id:
            order_vals['technician_ids'] = [(6, 0, [self.user_id.id])]
        order = self.env['maintenance.order'].with_context(from_ticket=True).create(order_vals)
        self.maintenance_order_id = order.id
        self.message_post(body=_('Orden de servicio creada automáticamente por categoría: %s') % order.name)
        return order

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            cat = ticket.category_id
            if cat:
                defaults = ticket._apply_category_defaults(cat)
                if defaults:
                    ticket.write(defaults)
                if cat.auto_create_maintenance_order and not ticket.maintenance_order_id and ticket.partner_id:
                    ticket._create_maintenance_order_from_ticket()
        return tickets

    def write(self, vals):
        res = super().write(vals)
        if 'category_id' in vals:
            for ticket in self:
                cat = ticket.category_id
                if cat:
                    defaults = ticket._apply_category_defaults(cat)
                    if defaults:
                        super(HelpdeskTicket, ticket).write(defaults)
                    if cat.auto_create_maintenance_order and not ticket.maintenance_order_id and ticket.partner_id:
                        ticket._create_maintenance_order_from_ticket()
        # Sincronizar asignado del ticket con la orden de mantenimiento (misma persona)
        if 'user_id' in vals:
            for ticket in self:
                if ticket.maintenance_order_id and ticket.user_id:
                    ticket.maintenance_order_id.technician_ids = [(6, 0, [ticket.user_id.id])]
        return res
    
    def action_convert_to_maintenance_order(self):
        """Crear orden de mantenimiento manualmente si no existe (por categoría ya puede existir)."""
        self.ensure_one()
        if self.maintenance_order_id:
            return {
                'name': _('Orden de Mantenimiento'),
                'type': 'ir.actions.act_window',
                'res_model': 'maintenance.order',
                'res_id': self.maintenance_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if not self.partner_id:
            raise UserError(_('El ticket debe tener un cliente para crear la orden de mantenimiento.'))
        desc = (self.name or '') + '\n\n' + (self.description or '')
        order_vals = {
            'partner_id': self.partner_id.id,
            'description': desc,
            'ticket_id': self.id,
        }
        if self.user_id:
            order_vals['technician_ids'] = [(6, 0, [self.user_id.id])]
        maintenance_order = self.env['maintenance.order'].create(order_vals)
        self.maintenance_order_id = maintenance_order.id
        self.message_post(body=_('Se creó una orden de mantenimiento: %s') % maintenance_order.name)
        return {
            'name': _('Orden de Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.order',
            'res_id': maintenance_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_escalate_ticket(self):
        """Abrir wizard para escalar el ticket a otro equipo o responsable (ej. Nivel 2)."""
        self.ensure_one()
        return {
            'name': _('Escalar ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket.escalate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'default_ticket_id': self.id},
        }
