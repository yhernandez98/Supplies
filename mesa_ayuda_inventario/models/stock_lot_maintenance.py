# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class StockLotMaintenance(models.Model):
    """Modelo para registrar mantenimientos, revisiones y trabajos realizados en productos serializados."""
    _name = 'stock.lot.maintenance'
    _description = 'Mantenimiento de Producto Serializado'
    _order = 'maintenance_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
<<<<<<< HEAD
        required=False,
=======
        required=True,
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
        ondelete='cascade',
        index=True,
        help='Producto serializado al que se le realizó el mantenimiento'
    )
    
<<<<<<< HEAD
    own_inventory_id = fields.Many2one(
        'customer.own.inventory',
        string='Producto Propio del Cliente',
        required=False,
        ondelete='cascade',
        index=True,
        help='Producto propio del cliente al que se le realizó el mantenimiento'
    )
    
    # Campos relacionados cuando se usa own_inventory_id
    own_inventory_product_id = fields.Many2one(
        'product.product',
        related='own_inventory_id.product_id',
        string='Producto (Propio)',
        store=True,
        readonly=True
    )
    
    own_inventory_customer_id = fields.Many2one(
        'res.partner',
        related='own_inventory_id.partner_id',
        string='Cliente (Propio)',
        store=True,
        readonly=True
    )
    
=======
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    product_id = fields.Many2one(
        'product.product',
        compute='_compute_product_customer',
        string='Producto',
        store=True,
        readonly=True
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        compute='_compute_product_customer',
        string='Cliente',
        store=True,
        readonly=True
    )
    
<<<<<<< HEAD
    @api.depends('lot_id.product_id', 'lot_id.customer_id', 'own_inventory_id.product_id', 'own_inventory_id.partner_id')
    def _compute_product_customer(self):
        """Obtener producto y cliente de lot_id o own_inventory_id."""
=======
    @api.depends('lot_id.product_id', 'lot_id.customer_id')
    def _compute_product_customer(self):
        """Obtener producto y cliente del lote."""
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
        for record in self:
            if record.lot_id:
                record.product_id = record.lot_id.product_id
                record.customer_id = record.lot_id.customer_id
<<<<<<< HEAD
            elif record.own_inventory_id:
                record.product_id = record.own_inventory_id.product_id
                record.customer_id = record.own_inventory_id.partner_id
=======
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
            else:
                record.product_id = False
                record.customer_id = False
    
    inventory_plate = fields.Char(
        related='lot_id.inventory_plate',
        string='Placa de Inventario',
        store=True,
        readonly=True,
        help='Placa de inventario del equipo'
    )
    
    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Orden de mantenimiento a la que pertenece este mantenimiento'
    )
    
    maintenance_date = fields.Datetime(
        string='Fecha de Mantenimiento',
        required=True,
        default=fields.Datetime.now,
        help='Fecha y hora en que se realizó el mantenimiento o revisión'
    )
    
    maintenance_type = fields.Selection([
        ('preventive', 'Mantenimiento Preventivo'),
        ('corrective', 'Mantenimiento Correctivo'),
        ('remote_support', 'Soporte Técnico Remoto'),
        ('onsite_support', 'Soporte Técnico en Sitio'),
        ('diagnosis', 'Diagnóstico y Evaluación'),
        ('installation', 'Instalación y Configuración'),
        ('server_implementation', 'Implementación de Servidores'),
        ('server_migration', 'Migración de Servidores'),
        ('backup_recovery', 'Backup y Recuperación'),
        ('firewall_vpn', 'Configuración de Firewall/VPN'),
        ('licensing_m365', 'Gestión de Licenciamiento M365'),
        ('admin_m365', 'Administración de M365 / SharePoint'),
        ('upgrade', 'Actualización / Mejora'),
        ('other', 'Otro'),
    ], string='Tipo de Servicio', required=True, default='diagnosis',
       help='Tipo de servicio o trabajo realizado')
    
    technician_id = fields.Many2one(
        'res.users',
        string='Técnico Principal',
        default=lambda self: self.env.user,
        required=True,
        help='Técnico principal que realizó el mantenimiento o revisión'
    )
    
    technician_ids = fields.Many2many(
        'res.users',
        'lot_maintenance_technician_rel',
        'maintenance_id',
        'user_id',
        string='Técnicos Asignados',
        help='Todos los técnicos asignados a este mantenimiento'
    )
    
    description = fields.Html(
        string='Descripción del Trabajo',
        required=True,
        sanitize=False,
        help='Descripción detallada del trabajo realizado con formato enriquecido. Puedes agregar imágenes y formato de texto.'
    )
    
    observations = fields.Html(
        string='Observaciones',
        sanitize=False,
        help='Observaciones adicionales, hallazgos o recomendaciones con formato enriquecido'
    )
    
    @api.onchange('maintenance_order_id')
    def _onchange_maintenance_order_id(self):
        """Cuando se selecciona una orden, copiar los técnicos asignados."""
        if self.maintenance_order_id and self.maintenance_order_id.technician_ids:
            self.technician_ids = [(6, 0, self.maintenance_order_id.technician_ids.ids)]
            if not self.technician_id and self.maintenance_order_id.technician_ids:
                self.technician_id = self.maintenance_order_id.technician_ids[0].id
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id.id,
        required=True,
        help='Moneda para el costo'
    )
    
    cost = fields.Monetary(
        string='Costo',
        currency_field='currency_id',
        help='Costo del mantenimiento o servicio realizado'
    )
    
    duration = fields.Float(
        string='Duración (Horas)',
        digits=(16, 2),
        help='Tiempo que tomó realizar el mantenimiento en horas'
    )
    
    status = fields.Selection([
        ('draft', 'Borrador'),
        ('scheduled', 'Programado'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
        ('pending', 'Pendiente'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True,
       help='Estado del mantenimiento. Se actualiza automáticamente a "Completado" cuando tiene ambas firmas.')
    
    technician_signature = fields.Binary(
        string='Firma del Técnico',
        help='Firma digital del técnico que realizó el mantenimiento',
        attachment=False  # Cambiar a False para que funcione con el widget signature
    )
    
    technician_signed_by = fields.Many2one(
        'res.users',
        string='Firmado por Técnico',
        readonly=True,
        help='Usuario técnico que firmó el mantenimiento'
    )
    
    technician_signed_date = fields.Datetime(
        string='Fecha Firma Técnico',
        readonly=True,
        help='Fecha y hora en que el técnico firmó'
    )
    
    customer_signature = fields.Binary(
        string='Firma del Cliente',
        help='Firma digital del cliente que aprueba el mantenimiento',
        attachment=False  # Cambiar a False para que funcione con el widget signature
    )
    
    customer_signed_by = fields.Many2one(
        'res.partner',
        string='Firmado por Cliente',
        readonly=True,
        help='Cliente que firmó el mantenimiento'
    )
    
    customer_signed_date = fields.Datetime(
        string='Fecha Firma Cliente',
        readonly=True,
        help='Fecha y hora en que el cliente firmó'
    )
    
    is_signed = fields.Boolean(
        string='Está Firmado',
        compute='_compute_is_signed',
        store=True,
        help='Indica si el mantenimiento tiene ambas firmas (técnico y cliente)'
    )
    
    show_warning_alert = fields.Boolean(
        string='Mostrar Alerta de Advertencia',
        compute='_compute_show_alerts',
        help='Indica si se debe mostrar la alerta de mantenimiento firmado'
    )
    
    show_info_alert = fields.Boolean(
        string='Mostrar Alerta Informativa',
        compute='_compute_show_alerts',
        help='Indica si se debe mostrar la alerta de borrador'
    )
    
    @api.depends('is_signed', 'status')
    def _compute_show_alerts(self):
        """Calcular qué alertas mostrar."""
        for record in self:
            record.show_warning_alert = record.is_signed
            record.show_info_alert = record.status == 'draft' and not record.is_signed
    
    next_maintenance_date = fields.Datetime(
        string='Próximo Mantenimiento',
        help='Fecha sugerida para el próximo mantenimiento'
    )
    
    # Campos temporalmente desactivados:
    component_change_ids = fields.One2many(
        'maintenance.component.change',
        'maintenance_id',
        string='Cambios de Componentes',
        help='Componentes cambiados durante este mantenimiento'
    )
    
    repair_order_id = fields.Many2one(
        'repair.order',
        string='Orden de Reparación',
        readonly=True,
        tracking=True,
        help='Orden de reparación generada desde este mantenimiento'
    )
    
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        readonly=True,
        tracking=True,
        help='Ticket asociado a este mantenimiento'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'lot_maintenance_attachment_rel',
        'maintenance_id',
        'attachment_id',
        string='Adjuntos',
        help='Documentos, fotos o archivos relacionados con este mantenimiento'
    )
    
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        help='Referencia única del mantenimiento'
    )
    
    @api.depends('technician_signature', 'customer_signature')
    def _compute_is_signed(self):
        """Calcular si el mantenimiento está completamente firmado."""
        for record in self:
            record.is_signed = bool(record.technician_signature and record.customer_signature)
    
    @api.onchange('technician_signature')
    def _onchange_technician_signature(self):
        """Cuando se carga una firma del técnico, guardar usuario y fecha automáticamente."""
        if self.technician_signature:
            if not self.technician_signed_by:
                self.technician_signed_by = self.env.user.id
            if not self.technician_signed_date:
                self.technician_signed_date = fields.Datetime.now()
    
    @api.onchange('customer_signature')
    def _onchange_customer_signature(self):
        """Cuando se carga una firma del cliente, guardar cliente y fecha automáticamente."""
        if self.customer_signature:
            if not self.customer_signed_by:
                # Obtener el cliente de diferentes fuentes
                customer_partner_id = None
                if self.lot_id and self.lot_id.customer_id:
                    customer_partner_id = self.lot_id.customer_id.id
                elif self.customer_id:
                    customer_partner_id = self.customer_id.id
                
                if customer_partner_id:
                    self.customer_signed_by = customer_partner_id
            
            if not self.customer_signed_date:
                self.customer_signed_date = fields.Datetime.now()
    
<<<<<<< HEAD
    @api.constrains('lot_id', 'own_inventory_id')
    def _check_lot_or_own_inventory(self):
        """Validar que al menos uno de los campos esté presente."""
        for record in self:
            if not record.lot_id and not record.own_inventory_id:
                raise UserError(_(
                    'Debe especificar un Número de Serie (stock.lot) o un Producto Propio del Cliente.'
                ))
    
    @api.depends('lot_id.name', 'own_inventory_id.serial_number', 'maintenance_date', 'maintenance_type')
=======
    @api.constrains('lot_id')
    def _check_lot_id(self):
        """Validar que el lote (equipo) esté presente."""
        for record in self:
            if not record.lot_id:
                raise UserError(_('Debe especificar un Número de Serie (equipo).'))
    
    @api.depends('lot_id.name', 'maintenance_date', 'maintenance_type')
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    def _compute_name(self):
        """Generar referencia única para cada mantenimiento."""
        for record in self:
            if record.maintenance_date:
                if isinstance(record.maintenance_date, str):
                    maintenance_dt = fields.Datetime.from_string(record.maintenance_date)
                else:
                    maintenance_dt = record.maintenance_date
                date_str = maintenance_dt.strftime('%Y%m%d')
                type_label = dict(record._fields['maintenance_type'].selection).get(record.maintenance_type, '')
                
<<<<<<< HEAD
                # Usar lot_id si existe, sino usar own_inventory_id
                if record.lot_id:
                    identifier = record.lot_id.name or 'LOT'
                elif record.own_inventory_id:
                    identifier = record.own_inventory_id.serial_number or record.own_inventory_id.product_id.name or 'OWN'
                else:
                    identifier = 'NEW'
=======
                identifier = record.lot_id.name if record.lot_id else 'NEW'
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
                
                record.name = "%s-%s-%s" % (identifier, date_str, type_label[:3].upper())
            else:
                record.name = 'Nuevo Mantenimiento'
    
    @api.model
    def create(self, vals):
        """Al crear un mantenimiento, enviar mensaje al chatter del lote."""
        # ✅ DESACTIVADO: Ya no es obligatorio tener ambas firmas
        # Validar firmas si se intenta guardar con estado diferente a borrador
        # if vals.get('status') and vals['status'] != 'draft':
        #     if not vals.get('technician_signature') or not vals.get('customer_signature'):
        #         raise UserError(_('No se puede guardar un mantenimiento sin las firmas del técnico y del cliente. Debe mantenerse como borrador hasta tener ambas firmas.'))
        
        # ✅ Crear automáticamente una orden de mantenimiento si no se proporciona una
        if 'maintenance_order_id' not in vals or not vals.get('maintenance_order_id'):
            # Obtener información del equipo y cliente
            lot_id = vals.get('lot_id')
            if lot_id:
                lot = self.env['stock.lot'].browse(lot_id)
                customer_id = lot.customer_id.id if hasattr(lot, 'customer_id') and lot.customer_id else False
                
                # Si hay cliente, crear orden de mantenimiento automáticamente
                if customer_id:
                    # Obtener técnico (del vals o del usuario actual)
                    technician_id = vals.get('technician_id', self.env.user.id)
                    
                    # Crear orden de mantenimiento automática
                    order_vals = {
                        'partner_id': customer_id,
                        'scheduled_date': vals.get('maintenance_date', fields.Datetime.now()),
                        'state': 'draft',
                        'technician_ids': [(6, 0, [technician_id])],
                    }
                    
                    order = self.env['maintenance.order'].create(order_vals)
                    vals['maintenance_order_id'] = order.id
        
        # Registrar firma del técnico si se proporciona
        if 'technician_signature' in vals and vals.get('technician_signature') and not vals.get('technician_signed_by'):
            vals['technician_signed_by'] = self.env.user.id
            vals['technician_signed_date'] = fields.Datetime.now()
        
        # Registrar firma del cliente si se proporciona
        if 'customer_signature' in vals and vals.get('customer_signature') and not vals.get('customer_signed_by'):
            if self.env.context.get('customer_partner_id'):
                vals['customer_signed_by'] = self.env.context['customer_partner_id']
            vals['customer_signed_date'] = fields.Datetime.now()
        
        # ✅ Si hay orden de mantenimiento, copiar los técnicos asignados
        if 'maintenance_order_id' in vals and vals.get('maintenance_order_id'):
            order = self.env['maintenance.order'].browse(vals['maintenance_order_id'])
            if order.technician_ids:
                # Si no se especificaron técnicos, usar los de la orden
                if 'technician_ids' not in vals or not vals.get('technician_ids'):
                    vals['technician_ids'] = [(6, 0, order.technician_ids.ids)]
                # Si no hay técnico principal, usar el primero de la orden
                if 'technician_id' not in vals or not vals.get('technician_id'):
                    vals['technician_id'] = order.technician_ids[0].id
        
        maintenance = super().create(vals)
        if maintenance.lot_id:
            maintenance.lot_id.message_post(
                body=_('Mantenimiento registrado: %s') % maintenance.description[:100] if maintenance.description else _('Nuevo mantenimiento'),
                subject=_('Nuevo Mantenimiento')
            )
        
        # ✅ Si el mantenimiento está asociado a una orden, actualizar el ticket
        if maintenance.maintenance_order_id and maintenance.maintenance_order_id.ticket_id:
            maintenance.maintenance_order_id._update_ticket_with_equipment()
        
        return maintenance
    
    def write(self, vals):
        """Al modificar un mantenimiento, validar firmas y restricciones."""
        # LOGGING INMEDIATO al inicio del método
        import sys
        print("=" * 80, file=sys.stderr)
        print("DEBUG: ===== INICIO WRITE - stock.lot.maintenance =====", file=sys.stderr)
        print("DEBUG: Todos los campos en vals:", list(vals.keys()), file=sys.stderr)
        print("DEBUG: IDs de registros:", [r.id for r in self], file=sys.stderr)
        if 'technician_signature' in vals:
            print("DEBUG: technician_signature ESTÁ en vals", file=sys.stderr)
        else:
            print("DEBUG: technician_signature NO está en vals", file=sys.stderr)
        if 'customer_signature' in vals:
            print("DEBUG: customer_signature ESTÁ en vals", file=sys.stderr)
        else:
            print("DEBUG: customer_signature NO está en vals", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        
        # Si está firmado, no permitir edición (excepto algunos campos)
        for record in self:
            if record.is_signed:
                allowed_fields = {'technician_signature', 'customer_signature', 'message_ids', 'message_follower_ids', 'activity_ids'}
                restricted_fields = set(vals.keys()) - allowed_fields
                if restricted_fields:
                    raise UserError(_('Este mantenimiento ya está firmado y no puede ser modificado. Los campos modificados fueron: %s') % ', '.join(restricted_fields))
        
        # No permitir cambiar el estado manualmente (excepto si viene de una orden de mantenimiento)
        if 'status' in vals and not self.env.context.get('skip_status_validation'):
            if 'technician_signature' not in vals and 'customer_signature' not in vals:
                for record in self:
                    if vals['status'] != record.status:
                        # Permitir cambios desde 'draft' a 'scheduled' o 'in_progress' si hay orden de mantenimiento
                        if record.maintenance_order_id:
                            # Si hay orden de mantenimiento, permitir cambios programáticos
                            if vals['status'] in ('scheduled', 'in_progress'):
                                continue
                        # ✅ DESACTIVADO: Ya no es obligatorio tener ambas firmas para completar
                        # if vals['status'] == 'completed' and not (record.technician_signature and record.customer_signature):
                        #     raise UserError(_('El estado no puede cambiarse manualmente. Se mantendrá como "Borrador" hasta que tenga las firmas del técnico y del cliente. Luego cambiará automáticamente a "Completado".'))
                        elif vals['status'] not in ('draft', 'scheduled', 'in_progress'):
                            raise UserError(_('El estado no puede cambiarse manualmente. Solo cambia automáticamente a "Completado" cuando se tienen ambas firmas, o desde la orden de mantenimiento.'))
        
        # Loguear TODOS los campos en vals para diagnóstico (usar WARNING para que aparezca en logs)
        _logger.warning("DEBUG: ===== INICIO WRITE - stock.lot.maintenance =====")
        _logger.warning("DEBUG: Todos los campos en vals: %s", list(vals.keys()))
        _logger.warning("DEBUG: IDs de registros: %s", [r.id for r in self])
        
        # NO INTERFERIR con el guardado de los campos Binary
        # Dejar que Odoo maneje los campos signature normalmente
        # Solo loguear para diagnóstico
        if 'technician_signature' in vals:
            tech_sig = vals.get('technician_signature')
            _logger.warning("DEBUG: technician_signature en vals - Tipo: %s, Presente: %s", 
                       type(tech_sig).__name__, 
                       bool(tech_sig and tech_sig not in (False, None, '', b'')))
        else:
            _logger.warning("DEBUG: technician_signature NO está en vals")
        
        if 'customer_signature' in vals:
            cust_sig = vals.get('customer_signature')
            _logger.warning("DEBUG: customer_signature en vals - Tipo: %s, Presente: %s", 
                       type(cust_sig).__name__, 
                       bool(cust_sig and cust_sig not in (False, None, '', b'')))
        else:
            _logger.warning("DEBUG: customer_signature NO está en vals")
        
        # Guardar los cambios SIN interferir
        result = super().write(vals)
        _logger.warning("DEBUG: Después de super().write(), registros guardados")
        
        # Verificar estado después de guardar
        for record in self:
            record.invalidate_recordset(['technician_signature', 'customer_signature'])
            _logger.warning("DEBUG: Después de guardar - Record ID %s: tech_sig=%s, cust_sig=%s", 
                        record.id, 
                        bool(record.technician_signature), 
                        bool(record.customer_signature))
        _logger.warning("DEBUG: ===== FIN WRITE =====")
        
        # Después de guardar, completar campos relacionados y actualizar estado si es necesario
        if not self.env.context.get('skip_signature_check'):
            self._post_write_process_signatures()
        
        return result
    
    def _post_write_process_signatures(self):
        """Procesar firmas después de guardar: completar campos relacionados y actualizar estado."""
        for record in self:
            # Limpiar caché para obtener valores actualizados
            record.invalidate_recordset(['technician_signature', 'customer_signature', 'status'])
            update_vals = {}
            
            # Si hay firma del técnico, asegurar que estén los campos relacionados
            if record.technician_signature:
                if not record.technician_signed_by:
                    update_vals['technician_signed_by'] = self.env.user.id
                if not record.technician_signed_date:
                    update_vals['technician_signed_date'] = fields.Datetime.now()
            
            # Si hay firma del cliente, asegurar que estén los campos relacionados
            if record.customer_signature:
                if not record.customer_signed_by:
                    customer_partner_id = None
                    if record.lot_id and record.lot_id.customer_id:
                        customer_partner_id = record.lot_id.customer_id.id
                    elif record.customer_id:
                        customer_partner_id = record.customer_id.id
                    
                    if customer_partner_id:
                        update_vals['customer_signed_by'] = customer_partner_id
                
                if not record.customer_signed_date:
                    update_vals['customer_signed_date'] = fields.Datetime.now()
            
            # Actualizar campos relacionados si faltaban
            if update_vals:
                record.with_context(skip_signature_check=True, skip_status_validation=True).write(update_vals)
                record.invalidate_recordset(['status'])
            
            # Si ambas firmas están presentes y el estado es borrador, cambiar a completado
            if record.technician_signature and record.customer_signature and record.status == 'draft':
                self.env.cr.execute(
                    "UPDATE stock_lot_maintenance SET status = %s WHERE id = %s",
                    ('completed', record.id)
                )
                record.invalidate_recordset(['status'])
                
                # Notificar al chatter
                if record.lot_id:
                    record.lot_id.message_post(
                        body=_('Estado del mantenimiento cambiado automáticamente a "Completado" porque tiene ambas firmas.'),
                        subject=_('Actualización de Mantenimiento')
                    )
    
    def action_convert_to_repair(self):
        """Convertir este mantenimiento en una orden de reparación, crear ticket hijo y actividad."""
        self.ensure_one()
        if self.repair_order_id:
            return {
                'name': _('Orden de Reparación'),
                'type': 'ir.actions.act_window',
                'res_model': 'repair.order',
                'res_id': self.repair_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        # Crear la orden de reparación
        repair_order = self.env['repair.order'].create_from_maintenance(self.id)
        
        # Crear ticket hijo si existe ticket padre o ticket en la orden
        child_ticket = None
        parent_ticket = None
        
        # Buscar ticket padre: puede ser del mantenimiento individual o de la orden
        if self.ticket_id:
            parent_ticket = self.ticket_id
        elif self.maintenance_order_id and self.maintenance_order_id.ticket_id:
            parent_ticket = self.maintenance_order_id.ticket_id
        
        # Crear ticket hijo para la reparación (siempre, incluso si no hay ticket padre)
        child_ticket = self.env['helpdesk.ticket'].create({
            'partner_id': self.customer_id.id if self.customer_id else False,
            'name': _('Reparación: %s - %s') % (
                repair_order.name or '',
                (self.description[:50] if self.description else '')[:100] if self.description else ''
            )[:100],
            'lot_id': self.lot_id.id if self.lot_id else False,
            'maintenance_id': self.id,
            'maintenance_order_id': self.maintenance_order_id.id if self.maintenance_order_id else False,
            'description': _('Ticket creado para la reparación desde el mantenimiento %s.\n\nOrden de Reparación: %s\n\nDescripción del problema:\n%s') % (
                self.name or '',
                repair_order.name or '',
                self.description or self.observations or ''
            ),
            'maintenance_category': 'repair',
        })
        
        # Si hay ticket padre, vincularlos mediante mensajes en el chatter
        if parent_ticket:
            parent_ticket.message_post(
                body=_('Se creó un ticket hijo para la reparación: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    child_ticket.id, child_ticket.name
                ),
                subject=_('Ticket hijo creado')
            )
            child_ticket.message_post(
                body=_('Este ticket está relacionado con el ticket padre: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    parent_ticket.id, parent_ticket.name
                ),
                subject=_('Relación con ticket padre')
            )
        
        # Vincular el ticket hijo a la reparación y al mantenimiento
        repair_order.write({
            'ticket_id': child_ticket.id,
        })
        self.write({'repair_order_id': repair_order.id})
        
        # Cambiar el estado del mantenimiento para indicar que generó una reparación
        self.message_post(body=_('Se generó una orden de reparación: <a href="#" data-oe-model="repair.order" data-oe-id="%s">%s</a>. Ticket asociado: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
            repair_order.id, repair_order.name,
            child_ticket.id, child_ticket.name
        ))
        
        # Abrir wizard para asignar la actividad
        return {
            'name': _('Asignar Actividad de Reparación'),
            'type': 'ir.actions.act_window',
            'res_model': 'activity.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_repair_order_id': repair_order.id,
                'default_maintenance_id': self.id,
            }
        }
    
    def action_create_ticket(self):
        """Crear un ticket desde este mantenimiento usando el módulo nativo."""
        self.ensure_one()
        ticket = self.env['helpdesk.ticket'].create({
            'partner_id': self.customer_id.id if self.customer_id else False,
            'name': _('Mantenimiento: %s - %s') % (self.lot_id.name or '', self.description[:50] if self.description else '')[:100],
            'lot_id': self.lot_id.id,
            'maintenance_id': self.id,
            'maintenance_order_id': self.maintenance_order_id.id if self.maintenance_order_id else False,
            'description': self.description or '',
            'maintenance_category': 'maintenance',
        })
        # Vincular el ticket al mantenimiento
        self.ticket_id = ticket.id
        self.message_post(body=_('Se creó un ticket: %s') % ticket.name)
        return {
            'name': _('Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_helpdesk_ticket(self):
        """Ver el ticket asociado."""
        self.ensure_one()
        if not self.ticket_id:
            raise UserError(_('Este mantenimiento no tiene un ticket asociado.'))
        return {
            'name': _('Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_repair_order(self):
        """Ver la orden de reparación asociada."""
        self.ensure_one()
        if not self.repair_order_id:
            raise UserError(_('Este mantenimiento no tiene una orden de reparación asociada.'))
        return {
            'name': _('Orden de Reparación'),
            'type': 'ir.actions.act_window',
            'res_model': 'repair.order',
            'res_id': self.repair_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_generate_pdf_report(self):
        """Generar reporte PDF del mantenimiento."""
        self.ensure_one()
        return self.env.ref('mesa_ayuda_inventario.action_report_stock_lot_maintenance').report_action(self)
    
    def action_equipment_change(self):
        """Abrir wizard para crear actividad de cambio de equipo."""
        self.ensure_one()
        return {
            'name': _('Cambio de Equipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.lot_id.id if self.lot_id else False,
                'default_maintenance_id': self.id,
                'default_partner_id': self.customer_id.id if self.customer_id else False,
            }
        }
    
    def action_request_element(self):
        """Abrir wizard para solicitar un elemento/componente."""
        self.ensure_one()
        return {
            'name': _('Solicitar Elemento/Componente'),
            'type': 'ir.actions.act_window',
            'res_model': 'request.element.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.lot_id.id if self.lot_id else False,
                'default_maintenance_id': self.id,
                'default_partner_id': self.customer_id.id if self.customer_id else False,
            }
        }
    
    def action_open_debug_logs(self):
        """Abrir ventana de debug y logs."""
        self.ensure_one()
        return self.env['mesa_ayuda.debug.log'].action_open_debug_log()
    
    def action_debug_signatures(self):
        """Botón de debug para verificar el estado de las firmas."""
        self.ensure_one()
        
        # Información de debug
        debug_info = []
        debug_info.append(f"=== DEBUG DE FIRMAS - Mantenimiento: {self.name} ===")
        debug_info.append(f"ID: {self.id}")
        debug_info.append(f"Estado: {self.status}")
        debug_info.append(f"")
        debug_info.append(f"--- Firma del Técnico ---")
        debug_info.append(f"  Firma presente: {bool(self.technician_signature)}")
        debug_info.append(f"  Tipo: {type(self.technician_signature)}")
        debug_info.append(f"  Valor: {repr(self.technician_signature)[:100] if self.technician_signature else 'None/False'}")
        debug_info.append(f"  Firmado por: {self.technician_signed_by.name if self.technician_signed_by else 'NO'}")
        debug_info.append(f"  Fecha: {self.technician_signed_date or 'NO'}")
        debug_info.append(f"")
        debug_info.append(f"--- Firma del Cliente ---")
        debug_info.append(f"  Firma presente: {bool(self.customer_signature)}")
        debug_info.append(f"  Tipo: {type(self.customer_signature)}")
        debug_info.append(f"  Valor: {repr(self.customer_signature)[:100] if self.customer_signature else 'None/False'}")
        debug_info.append(f"  Firmado por: {self.customer_signed_by.name if self.customer_signed_by else 'NO'}")
        debug_info.append(f"  Fecha: {self.customer_signed_date or 'NO'}")
        debug_info.append(f"")
        debug_info.append(f"--- Estado Computado ---")
        debug_info.append(f"  Está Firmado (is_signed): {self.is_signed}")
        
        # Verificar attachments para las firmas (campos Binary con attachment=True se guardan aquí)
        attachments_tech = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
            ('name', '=', 'technician_signature'),
        ], limit=1)
        
        attachments_cust = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
            ('name', '=', 'customer_signature'),
        ], limit=1)
        
        debug_info.append(f"")
        debug_info.append(f"--- Attachments en ir_attachment ---")
        debug_info.append(f"  Attachment técnico: {'SÍ' if attachments_tech else 'NO'}")
        if attachments_tech:
            debug_info.append(f"    - Tamaño: {attachments_tech.file_size or 0} bytes")
            debug_info.append(f"    - Tipo: {attachments_tech.mimetype or 'N/A'}")
        debug_info.append(f"  Attachment cliente: {'SÍ' if attachments_cust else 'NO'}")
        if attachments_cust:
            debug_info.append(f"    - Tamaño: {attachments_cust.file_size or 0} bytes")
            debug_info.append(f"    - Tipo: {attachments_cust.mimetype or 'N/A'}")
        
        # Verificar todos los attachments del registro
        all_attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
        ])
        debug_info.append(f"")
        debug_info.append(f"--- Todos los Attachments del Registro ---")
        debug_info.append(f"  Total: {len(all_attachments)}")
        for att in all_attachments[:5]:  # Mostrar solo los primeros 5
            debug_info.append(f"    - {att.name}: {att.file_size or 0} bytes")
        
        # Intentar actualizar estado si ambas firmas están presentes
        if self.technician_signature and self.customer_signature and self.status == 'draft':
            debug_info.append(f"")
            debug_info.append(f"=== INTENTANDO ACTUALIZAR ESTADO ===")
            try:
                self.with_context(skip_signature_check=True, skip_status_validation=True).write({'status': 'completed'})
                debug_info.append(f"✓ Estado actualizado a 'Completado'")
            except Exception as e:
                debug_info.append(f"✗ Error al actualizar estado: {str(e)}")
        
        # Mostrar mensaje
        message = "\n".join(debug_info)
        raise UserError(message)
    
    def action_debug_server_info(self):
        """Botón de debug avanzado que muestra información del servidor y del request."""
        self.ensure_one()
        
        debug_info = []
        debug_info.append("=" * 80)
        debug_info.append("=== DEBUG AVANZADO DEL SERVIDOR - Mantenimiento: %s ===" % self.name)
        debug_info.append("=" * 80)
        debug_info.append("")
        
        # Información básica del registro
        debug_info.append("--- INFORMACIÓN DEL REGISTRO ---")
        debug_info.append("  ID: %s" % self.id)
        debug_info.append("  Nombre: %s" % self.name)
        debug_info.append("  Estado: %s" % self.status)
        debug_info.append("  Creado: %s" % (self.create_date or 'N/A'))
        debug_info.append("  Última modificación: %s" % (self.write_date or 'N/A'))
        debug_info.append("")
        
        # Estado actual de las firmas en el ORM
        debug_info.append("--- ESTADO DE FIRMAS (ORM) ---")
        debug_info.append("  Firma Técnico:")
        debug_info.append("    - Presente: %s" % bool(self.technician_signature))
        debug_info.append("    - Tipo: %s" % type(self.technician_signature).__name__)
        debug_info.append("    - Firmado por: %s" % (self.technician_signed_by.name if self.technician_signed_by else 'NO'))
        debug_info.append("    - Fecha: %s" % (self.technician_signed_date or 'NO'))
        debug_info.append("")
        debug_info.append("  Firma Cliente:")
        debug_info.append("    - Presente: %s" % bool(self.customer_signature))
        debug_info.append("    - Tipo: %s" % type(self.customer_signature).__name__)
        debug_info.append("    - Firmado por: %s" % (self.customer_signed_by.name if self.customer_signed_by else 'NO'))
        debug_info.append("    - Fecha: %s" % (self.customer_signed_date or 'NO'))
        debug_info.append("")
        
        # Verificar en la base de datos directamente (SQL)
        debug_info.append("--- VERIFICACIÓN EN BASE DE DATOS (SQL) ---")
        try:
            self.env.cr.execute("""
                SELECT 
                    id, name, status, create_date, write_date,
                    technician_signed_by, technician_signed_date,
                    customer_signed_by, customer_signed_date
                FROM stock_lot_maintenance 
                WHERE id = %s
            """, (self.id,))
            row = self.env.cr.fetchone()
            if row:
                db_id, db_name, db_status, db_create, db_write, db_tech_by, db_tech_date, db_cust_by, db_cust_date = row
                debug_info.append("  ID en BD: %s" % db_id)
                debug_info.append("  Estado en BD: %s" % db_status)
                debug_info.append("  Firmado por Técnico (ID): %s" % (db_tech_by or 'NULL'))
                debug_info.append("  Fecha Firma Técnico: %s" % (db_tech_date or 'NULL'))
                debug_info.append("  Firmado por Cliente (ID): %s" % (db_cust_by or 'NULL'))
                debug_info.append("  Fecha Firma Cliente: %s" % (db_cust_date or 'NULL'))
        except Exception as e:
            debug_info.append("  Error al consultar BD: %s" % str(e))
        debug_info.append("")
        
        # Verificar attachments (para campos Binary con attachment=True)
        debug_info.append("--- ATTACHMENTS EN ir_attachment ---")
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
        ])
        debug_info.append("  Total attachments: %s" % len(attachments))
        for att in attachments:
            debug_info.append("    - %s: %s bytes (%s)" % (att.name or 'Sin nombre', att.file_size or 0, att.mimetype or 'N/A'))
        debug_info.append("")
        
        # Verificar si hay attachments específicos para las firmas
        tech_att = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
            ('name', '=', 'technician_signature'),
        ], limit=1)
        cust_att = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.lot.maintenance'),
            ('res_id', '=', self.id),
            ('name', '=', 'customer_signature'),
        ], limit=1)
        
        debug_info.append("  Attachment Firma Técnico: %s" % ('SÍ' if tech_att else 'NO'))
        if tech_att:
            debug_info.append("    - Tamaño: %s bytes" % (tech_att.file_size or 0))
        debug_info.append("  Attachment Firma Cliente: %s" % ('SÍ' if cust_att else 'NO'))
        if cust_att:
            debug_info.append("    - Tamaño: %s bytes" % (cust_att.file_size or 0))
        debug_info.append("")
        
        # Información del contexto actual
        debug_info.append("--- INFORMACIÓN DEL CONTEXTO ---")
        debug_info.append("  Usuario actual: %s (ID: %s)" % (self.env.user.name, self.env.user.id))
        debug_info.append("  Contexto: %s" % str(self.env.context))
        debug_info.append("")
        
        # Verificar campos del modelo
        debug_info.append("--- CAMPOS DEL MODELO ---")
        model_fields = self._fields
        sig_fields = [f for f in model_fields.keys() if 'signature' in f or 'signed' in f]
        for field_name in sorted(sig_fields):
            field = model_fields.get(field_name)
            if field:
                value = getattr(self, field_name, None)
                debug_info.append("  %s: %s (tipo: %s)" % (field_name, value, type(value).__name__))
        debug_info.append("")
        
        # Intentar leer el valor directamente desde la BD usando el ORM
        debug_info.append("--- LECTURA DIRECTA DESDE ORM ---")
        try:
            self.invalidate_recordset(['technician_signature', 'customer_signature'])
            debug_info.append("  Después de invalidate_recordset:")
            debug_info.append("    - Firma Técnico: %s" % bool(self.technician_signature))
            debug_info.append("    - Firma Cliente: %s" % bool(self.customer_signature))
        except Exception as e:
            debug_info.append("  Error al invalidar: %s" % str(e))
        debug_info.append("")
        
        # Información sobre el widget signature
        debug_info.append("--- INFORMACIÓN SOBRE WIDGET SIGNATURE ---")
        tech_field = self._fields.get('technician_signature')
        cust_field = self._fields.get('customer_signature')
        debug_info.append("  Campo technician_signature:")
        if tech_field:
            debug_info.append("    - Tipo de campo: %s" % tech_field.type)
            debug_info.append("    - attachment: %s" % getattr(tech_field, 'attachment', False))
        debug_info.append("    - Widget en vista: signature")
        debug_info.append("  Campo customer_signature:")
        if cust_field:
            debug_info.append("    - Tipo de campo: %s" % cust_field.type)
            debug_info.append("    - attachment: %s" % getattr(cust_field, 'attachment', False))
        debug_info.append("    - Widget en vista: signature")
        debug_info.append("")
        
        # Mensaje final
        debug_info.append("=" * 80)
        debug_info.append("FIN DEL DEBUG")
        debug_info.append("=" * 80)
        
        message = "\n".join(debug_info)
        raise UserError(message)

