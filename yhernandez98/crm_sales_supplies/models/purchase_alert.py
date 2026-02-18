# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PurchaseAlert(models.Model):
    """Alerta por cotización cuando falta stock para una cotización."""
    _name = 'purchase.alert'
    _description = 'Alerta Por Cotización por Falta de Stock'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        default=lambda self: _('Nueva Alerta'),
        readonly=True,
        copy=False,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=False,
        readonly=True,
        ondelete='cascade',
        tracking=True,
        help='Orden de venta relacionada (opcional si se crea directamente desde Lead)',
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Línea de Venta',
        readonly=True,
        ondelete='cascade',
        tracking=True,
        help='Línea de venta relacionada (puede estar vacía si viene de especificación de equipo)',
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead/Oportunidad',
        required=True,
        readonly=True,
        store=True,
        tracking=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        readonly=True,
        store=True,
        tracking=True,
        help='Cliente relacionado (del Lead o de la orden de venta)',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto Principal',
        readonly=True,
        store=True,
        help='Producto principal de la alerta (si hay solo uno)',
    )
    quantity_requested = fields.Float(
        string='Cantidad Solicitada',
        compute='_compute_total_quantities',
        readonly=True,
        store=False,
        help='Cantidad total solicitada (suma de todas las líneas)',
    )
    quantity_available = fields.Float(
        string='Stock Disponible',
        compute='_compute_total_quantities',
        readonly=True,
        store=False,
        help='Stock disponible total (suma de todas las líneas)',
    )
    quantity_missing = fields.Float(
        string='Cantidad Faltante',
        compute='_compute_total_quantities',
        readonly=True,
        store=False,
        help='Cantidad faltante total (suma de todas las líneas)',
    )
    # Líneas de productos en la alerta
    alert_line_ids = fields.One2many(
        'purchase.alert.line',
        'alert_id',
        string='Productos a Cotizar',
        help='Lista de productos que se necesitan cotizar en esta alerta',
    )
    has_multiple_products = fields.Boolean(
        string='Múltiples Productos',
        compute='_compute_has_multiple_products',
        store=False,
        help='Indica si la alerta tiene múltiples productos',
    )
    user_has_crm_access = fields.Boolean(
        string='Usuario tiene Acceso CRM',
        compute='_compute_user_has_crm_access_instance',
        store=False,
        help='Indica si el usuario actual tiene acceso de CRM (no solo compras)',
    )
    
    @api.model
    def _compute_user_has_crm_access(self):
        """Calcular si el usuario tiene acceso de CRM."""
        user = self.env.user
        # Verificar si el usuario tiene acceso de ventas/CRM pero NO solo de compras
        has_sales_access = user.has_group('sales_team.group_sale_manager') or user.has_group('sales_team.group_sale_salesman')
        has_only_purchase = user.has_group('purchase.group_purchase_user') and not has_sales_access
        return not has_only_purchase
    
    def _compute_user_has_crm_access_instance(self):
        """Calcular si el usuario tiene acceso de CRM (método de instancia)."""
        for alert in self:
            alert.user_has_crm_access = self._compute_user_has_crm_access()
    
    @api.depends('alert_line_ids')
    def _compute_has_multiple_products(self):
        """Calcular si hay múltiples productos."""
        for alert in self:
            alert.has_multiple_products = len(alert.alert_line_ids) > 1
    
    @api.depends('alert_line_ids.quantity_requested', 'alert_line_ids.quantity_available', 'alert_line_ids.quantity_missing')
    def _compute_total_quantities(self):
        """Calcular totales de cantidad solicitada, disponible y faltante."""
        for alert in self:
            if alert.alert_line_ids:
                alert.quantity_requested = sum(alert.alert_line_ids.mapped('quantity_requested'))
                alert.quantity_available = sum(alert.alert_line_ids.mapped('quantity_available'))
                alert.quantity_missing = sum(alert.alert_line_ids.mapped('quantity_missing'))
            else:
                # Si no hay líneas, usar valores del producto principal (compatibilidad hacia atrás)
                alert.quantity_requested = alert.product_id and 1.0 or 0.0
                alert.quantity_available = 0.0
                alert.quantity_missing = alert.quantity_requested
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra Principal',
        readonly=True,
        tracking=True,
        compute='_compute_purchase_order_id',
        store=True,
        help='Orden de compra principal creada para satisfacer esta alerta (si solo se creó una)',
    )
    
    @api.depends('purchase_order_ids')
    def _compute_purchase_order_id(self):
        """Calcular orden de compra principal (primera de la lista)."""
        for alert in self:
            if alert.purchase_order_ids:
                alert.purchase_order_id = alert.purchase_order_ids[0]
            else:
                alert.purchase_order_id = False
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        'purchase_alert_purchase_order_rel',
        'alert_id',
        'purchase_order_id',
        string='Cotizaciones Solicitadas',
        readonly=True,
        help='Todas las cotizaciones solicitadas para esta alerta',
    )
    purchase_order_count = fields.Integer(
        string='Número de Cotizaciones',
        compute='_compute_purchase_order_count',
        readonly=True,
        help='Número de cotizaciones creadas para esta alerta',
    )
    
    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        """Calcular número de cotizaciones."""
        for alert in self:
            alert.purchase_order_count = len(alert.purchase_order_ids)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('purchase_created', 'Cotización solicitada'),
        ('sent', 'Orden Enviada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='pending', tracking=True, required=True)
    
    validated_by_crm = fields.Boolean(
        string='Validado por CRM',
        default=False,
        tracking=True,
        help='Indica si el jefe de CRM ha validado las cotizaciones creadas',
    )
    validated_by_user_id = fields.Many2one(
        'res.users',
        string='Validado por',
        readonly=True,
        tracking=True,
        help='Usuario de CRM que validó las cotizaciones',
    )
    validated_date = fields.Datetime(
        string='Fecha de Validación',
        readonly=True,
        tracking=True,
    )
    validation_notes = fields.Text(
        string='Notas de Validación',
        help='Comentarios del jefe de compras sobre la validación de las cotizaciones',
    )
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre la alerta de compra',
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        required=True,
        readonly=True,
        store=True,
        help='Almacén donde se verificará el stock',
    )

    # Campos para mostrar componentes, periféricos y complementos
    component_line_ids = fields.One2many(
        'purchase.alert.component.line',
        'alert_id',
        string='Componentes',
        help='Componentes del producto principal que deben cotizarse',
        domain=[('item_type', '=', 'component')],
    )
    peripheral_line_ids = fields.One2many(
        'purchase.alert.component.line',
        'alert_id',
        string='Periféricos',
        help='Periféricos del producto principal que deben cotizarse',
        domain=[('item_type', '=', 'peripheral')],
    )
    complement_line_ids = fields.One2many(
        'purchase.alert.component.line',
        'alert_id',
        string='Complementos',
        help='Complementos del producto principal que deben cotizarse',
        domain=[('item_type', '=', 'complement')],
    )
    
    # Campo para unificar todas las líneas en una sola vista (usando el mismo One2many)
    all_component_lines = fields.One2many(
        'purchase.alert.component.line',
        'alert_id',
        string='Todos los Elementos',
        help='Todos los componentes, periféricos y complementos unificados',
    )
    
    @api.model
    def create(self, vals):
        """Crear líneas de componentes al crear la alerta."""
        # Generar nombre automático para la alerta
        if not vals.get('name') or vals.get('name') == _('Nueva Alerta'):
            try:
                seq = self.env['ir.sequence'].next_by_code('purchase.alert') or _('Nueva Alerta')
            except Exception:
                seq = _('Nueva Alerta')
            vals['name'] = seq
        
        # Asignar partner_id desde lead_id si no está definido
        if not vals.get('partner_id') and vals.get('lead_id'):
            lead = self.env['crm.lead'].browse(vals['lead_id'])
            if lead and lead.partner_id:
                vals['partner_id'] = lead.partner_id.id
        
        # Asignar lead_id desde sale_order_id si no está definido
        if not vals.get('lead_id') and vals.get('sale_order_id'):
            sale_order = self.env['sale.order'].browse(vals['sale_order_id'])
            if sale_order and sale_order.opportunity_id:
                vals['lead_id'] = sale_order.opportunity_id.id
        
        # Crear la alerta
        alert = super().create(vals)
        
        # Actualizar líneas después de crear (necesitamos el ID)
        if alert.alert_line_ids or alert.product_id:
            alert._update_component_lines()
        
        return alert
    
    
    def _delete_existing_component_lines(self):
        """Eliminar todas las líneas de componentes existentes para esta alerta."""
        self.ensure_one()
        if not self.id:
            return
        
        # Buscar y eliminar todas las líneas existentes
        existing_lines = self.env['purchase.alert.component.line'].sudo().search([
            ('alert_id', '=', self.id)
        ])
        if existing_lines:
            _logger.info("Eliminando %s líneas existentes para alerta %s", len(existing_lines), self.id)
            existing_lines.unlink()
            # NO invalidar cache aquí para evitar bucles infinitos
    
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Sobrescribir search - NO crear líneas automáticamente para evitar duplicados."""
        result = super()._search(domain, offset=offset, limit=limit, order=order)
        # NO crear líneas automáticamente aquí - solo se crearán en create() o write()
        # Esto evita duplicados cuando se valida o se accede a una alerta existente
        return result
    
    def write(self, vals):
        """Actualizar líneas de componentes cuando cambia el producto, cantidad o alert_line_ids."""
        # Actualizar líneas si cambia el producto, cantidad o alert_line_ids
        should_update_lines = 'product_id' in vals or 'quantity_requested' in vals or 'alert_line_ids' in vals
        
        result = super().write(vals)
        
        if should_update_lines:
            for alert in self:
                if alert.id and (alert.alert_line_ids or alert.product_id):
                    alert._update_component_lines()
        
        return result
    
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """Sobrescribir para asegurar que las líneas se carguen."""
        result = super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return result
    
    def action_refresh_component_lines(self):
        """Acción para refrescar manualmente las líneas de componentes."""
        self.ensure_one()
        if self.alert_line_ids or self.product_id:
            self._update_component_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Líneas actualizadas'),
                'message': _('Las líneas de componentes, periféricos y complementos han sido actualizadas.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_delete_component_lines(self):
        """Acción para eliminar todas las líneas de componentes."""
        self.ensure_one()
        if self.id:
            self._delete_existing_component_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Líneas eliminadas'),
                'message': _('Todas las líneas de componentes, periféricos y complementos han sido eliminadas.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_notify_purchase_team(self):
        """Notificar al equipo de compras sobre esta alerta."""
        self.ensure_one()
        
        # Buscar usuarios del grupo de compras
        purchase_group = self.env.ref('purchase.group_purchase_user', raise_if_not_found=False)
        purchase_users = purchase_group.users if purchase_group else self.env['res.users']
        
        # Crear mensaje
        message_body = _('''
        <div class="o_mail_notification">
            <p><strong>📢 Notificación de Alerta de Compra</strong></p>
            <p><strong>Alerta:</strong> %s</p>
            <p><strong>Cliente:</strong> %s</p>
            <p><strong>Producto:</strong> %s</p>
            <p><strong>Cantidad Faltante:</strong> %s</p>
            <p><strong>Estado:</strong> %s</p>
            <p>Por favor, revise esta alerta y proporcione información sobre la disponibilidad o alternativas.</p>
        </div>
        ''') % (
            self.name,
            self.partner_id.display_name if self.partner_id else 'N/A',
            self.product_id.display_name if self.product_id else 'N/A',
            self.quantity_missing,
            dict(self._fields['state'].selection).get(self.state, self.state)
        )
        
        # Enviar mensaje
        self.message_post(
            body=message_body,
            subject=_('Notificación: %s') % self.name,
            partner_ids=purchase_users.partner_id.ids,
            message_type='notification',
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notificación enviada'),
                'message': _('Se ha notificado al equipo de compras sobre esta alerta.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_validate_purchase(self):
        """Validar las cotizaciones por el jefe de CRM."""
        self.ensure_one()
        
        if not self.purchase_order_ids:
            raise UserError(_('No hay cotizaciones para validar. Primero debe crear cotizaciones.'))
        
        # Abrir wizard para validar
        return {
            'type': 'ir.actions.act_window',
            'name': _('Validar Cotizaciones'),
            'res_model': 'purchase.alert.validation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_alert_id': self.id,
                'default_purchase_order_ids': [(6, 0, self.purchase_order_ids.ids)],
            },
        }
    
    def action_notify_creator_quotations_ready(self):
        """Crear una actividad para el usuario que creó la alerta informándole que las cotizaciones están listas para validar."""
        self.ensure_one()
        
        if not self.purchase_order_ids:
            raise UserError(_('No hay cotizaciones creadas para esta alerta.'))
        
        if not self.create_uid:
            raise UserError(_('No se puede identificar el usuario que creó esta alerta.'))
        
        # Contar cotizaciones pendientes de validación
        pending_quotations = self.purchase_order_ids.filtered(
            lambda po: po.state in ('draft', 'sent', 'to approve') and not po.approved_by_crm and not po.rejected_by_crm
        )
        total_quotations = len(self.purchase_order_ids)
        pending_count = len(pending_quotations)
        
        # Crear mensaje descriptivo
        if pending_count == total_quotations:
            message = _(
                'Las cotizaciones solicitadas para la alerta %s están listas para validar.\n\n'
                'Total de cotizaciones: %d\n'
                'Cliente: %s\n\n'
                'Por favor, revisa las cotizaciones y valida las que consideres apropiadas.'
            ) % (self.name, total_quotations, self.partner_id.display_name if self.partner_id else 'N/A')
        else:
            validated_count = total_quotations - pending_count
            message = _(
                'Hay nuevas cotizaciones listas para validar en la alerta %s.\n\n'
                'Total de cotizaciones: %d\n'
                'Pendientes de validación: %d\n'
                'Ya validadas: %d\n'
                'Cliente: %s\n\n'
                'Por favor, revisa las cotizaciones pendientes y valida las que consideres apropiadas.'
            ) % (
                self.name, 
                total_quotations, 
                pending_count, 
                validated_count,
                self.partner_id.display_name if self.partner_id else 'N/A'
            )
        
        # Buscar el tipo de actividad apropiado o crear uno genérico
        activity_type = self.env['mail.activity.type'].search([
            ('name', 'ilike', 'Validar')
        ], limit=1)
        
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([
                ('name', '=', 'To Do')
            ], limit=1)
        
        # Crear la actividad
        activity_vals = {
            'res_id': self.id,
            'res_model_id': self.env['ir.model']._get_id('purchase.alert'),
            'activity_type_id': activity_type.id if activity_type else False,
            'user_id': self.create_uid.id,
            'summary': _('Cotizaciones listas para validar - Alerta %s') % self.name,
            'note': message,
            'date_deadline': fields.Date.today(),
        }
        
        activity = self.env['mail.activity'].create(activity_vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actividad Creada'),
                'message': _('Se ha creado una actividad para %s informándole que las cotizaciones están listas para validar.') % self.create_uid.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_purchase_orders(self):
        """Ver el contenido detallado de las cotizaciones creadas."""
        self.ensure_one()
        
        if not self.purchase_order_ids:
            raise UserError(_('No hay cotizaciones creadas para esta alerta.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cotizaciones de Compra - %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'context': {
                'create': False,
                'default_origin': self.name,
            },
            'views': [
                (False, 'list'),
                (False, 'form'),
            ],
        }
    
    def action_unvalidate_purchase(self):
        """Desvalidar las cotizaciones."""
        self.ensure_one()
        
        self.write({
            'validated_by_crm': False,
            'validated_by_user_id': False,
            'validated_date': False,
            'validation_notes': False,
        })
        
        # Enviar mensaje
        self.message_post(
            body=_('❌ La validación de las cotizaciones ha sido removida por %s') % self.env.user.name,
            subject=_('Validación removida: %s') % self.name,
            message_type='notification',
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación removida'),
                'message': _('La validación de las cotizaciones ha sido removida.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def _update_component_lines(self):
        """Actualizar las líneas de componentes, periféricos y complementos."""
        self.ensure_one()
        
        _logger.info("_update_component_lines llamado para alerta %s", self.id)
        
        # Si no hay ID, no hacer nada
        if not self.id:
            return
        
        # SIEMPRE eliminar líneas existentes ANTES de crear nuevas para evitar duplicados
        self._delete_existing_component_lines()
        
        # Si hay múltiples productos, mostrar componentes de todos los productos
        # Verificar directamente si hay más de una línea en lugar de depender del campo computed
        has_multiple = len(self.alert_line_ids) > 1
        if has_multiple and self.alert_line_ids:
            _logger.info("Alerta tiene múltiples productos, mostrando componentes de todos")
            ComponentLine = self.env['purchase.alert.component.line'].sudo()
            component_lines = []
            peripheral_lines = []
            complement_lines = []
            
            # Recopilar componentes de todos los productos
            for alert_line in self.alert_line_ids:
                if not alert_line.product_id:
                    continue
                
                parent_product = alert_line.product_id
                template = parent_product.product_tmpl_id
                qty_multiplier = alert_line.quantity_requested or 1.0
                
                # Componentes
                for comp_line in template.composite_line_ids:
                    if comp_line.component_product_id:
                        component_lines.append({
                            'alert_id': self.id,
                            'product_id': comp_line.component_product_id.id,
                            'quantity': comp_line.component_qty * qty_multiplier,
                            'uom_id': comp_line.component_product_id.uom_id.id,
                            'item_type': 'component',
                            'parent_product_id': parent_product.id,
                        })
                
                # Periféricos
                for per_line in template.peripheral_line_ids:
                    if per_line.peripheral_product_id:
                        peripheral_lines.append({
                            'alert_id': self.id,
                            'product_id': per_line.peripheral_product_id.id,
                            'quantity': per_line.peripheral_qty * qty_multiplier,
                            'uom_id': per_line.peripheral_product_id.uom_id.id,
                            'item_type': 'peripheral',
                            'parent_product_id': parent_product.id,
                        })
                
                # Complementos
                for comp_line in template.complement_line_ids:
                    if comp_line.complement_product_id:
                        complement_lines.append({
                            'alert_id': self.id,
                            'product_id': comp_line.complement_product_id.id,
                            'quantity': comp_line.complement_qty * qty_multiplier,
                            'uom_id': comp_line.complement_product_id.uom_id.id,
                            'item_type': 'complement',
                            'parent_product_id': parent_product.id,
                        })
            
            # Crear todas las líneas
            if component_lines:
                ComponentLine.create(component_lines)
            if peripheral_lines:
                ComponentLine.create(peripheral_lines)
            if complement_lines:
                ComponentLine.create(complement_lines)
            
            _logger.info("Creadas %s líneas de componentes, %s de periféricos, %s de complementos",
                        len(component_lines), len(peripheral_lines), len(complement_lines))
            return
        
        # Si hay un solo producto principal
        if not self.product_id:
            _logger.info("No hay producto principal definido")
            return
        
        template = self.product_id.product_tmpl_id
        # Usar cantidad del producto principal o de la primera línea
        if self.alert_line_ids:
            qty_multiplier = self.alert_line_ids[0].quantity_requested or 1.0
        else:
            qty_multiplier = self.quantity_requested or 1.0
        
        _logger.info("Template: %s, Componentes: %s, Periféricos: %s, Complementos: %s", 
                    template.name,
                    len(template.composite_line_ids),
                    len(template.peripheral_line_ids),
                    len(template.complement_line_ids))
        
        ComponentLine = self.env['purchase.alert.component.line'].sudo()
        
        # Componentes
        component_lines = []
        for comp_line in template.composite_line_ids:
            if comp_line.component_product_id:
                component_lines.append({
                    'alert_id': self.id,
                    'product_id': comp_line.component_product_id.id,
                    'quantity': comp_line.component_qty * qty_multiplier,
                    'uom_id': comp_line.component_uom_id.id or comp_line.component_product_id.uom_id.id,
                    'item_type': 'component',
                    'parent_product_id': self.product_id.id,
                })
        if component_lines:
            _logger.info("Creando %s líneas de componentes", len(component_lines))
            created = ComponentLine.create(component_lines)
            _logger.info("Líneas de componentes creadas: %s", created.ids)
        else:
            _logger.info("No hay componentes para crear")
        
        # Periféricos
        peripheral_lines = []
        for peri_line in template.peripheral_line_ids:
            if peri_line.peripheral_product_id:
                peripheral_lines.append({
                    'alert_id': self.id,
                    'product_id': peri_line.peripheral_product_id.id,
                    'quantity': peri_line.peripheral_qty * qty_multiplier,
                    'uom_id': peri_line.peripheral_uom_id.id or peri_line.peripheral_product_id.uom_id.id,
                    'item_type': 'peripheral',
                    'parent_product_id': self.product_id.id,
                })
        if peripheral_lines:
            _logger.info("Creando %s líneas de periféricos", len(peripheral_lines))
            created = ComponentLine.create(peripheral_lines)
            _logger.info("Líneas de periféricos creadas: %s", created.ids)
        else:
            _logger.info("No hay periféricos para crear")
        
        # Complementos
        complement_lines = []
        for compl_line in template.complement_line_ids:
            if compl_line.complement_product_id:
                complement_lines.append({
                    'alert_id': self.id,
                    'product_id': compl_line.complement_product_id.id,
                    'quantity': compl_line.complement_qty * qty_multiplier,
                    'uom_id': compl_line.complement_uom_id.id or compl_line.complement_product_id.uom_id.id,
                    'item_type': 'complement',
                    'parent_product_id': self.product_id.id,
                })
        if complement_lines:
            _logger.info("Creando %s líneas de complementos", len(complement_lines))
            created = ComponentLine.create(complement_lines)
            _logger.info("Líneas de complementos creadas: %s", created.ids)
        else:
            _logger.info("No hay complementos para crear")
        
        # NO invalidar cache para evitar bucles infinitos


    @api.model
    def action_create_purchase_order(self):
        """Crear orden de compra desde la alerta (método rápido - un solo proveedor)."""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('Solo se pueden crear compras desde alertas pendientes.'))

        if not self.product_id:
            raise UserError(_('No se puede crear una orden de compra para una alerta sin producto definido.'))

        # Buscar proveedor del producto
        uom = self.sale_order_line_id.product_uom if self.sale_order_line_id else self.product_id.uom_id
        supplier = self.product_id._select_seller(
            partner_id=False,
            quantity=self.quantity_missing,
            date=fields.Date.today(),
            uom_id=uom,
        )
        if not supplier:
            raise UserError(_('No se encontró proveedor para el producto %s.') % self.product_id.display_name)

        # Crear orden de compra
        purchase_vals = {
            'partner_id': supplier.partner_id.id,
            'origin': self.sale_order_id.name,
            'picking_type_id': self.warehouse_id.in_type_id.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_qty': self.quantity_missing,
                'product_uom': uom.id,
                'price_unit': supplier.price or self.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
                'name': _('Para cliente: %s - %s') % (self.partner_id.display_name, self.sale_order_id.name),
            })],
            # Campo personalizado para vincular con venta
            'sale_order_ids': [(4, self.sale_order_id.id)],
        }
        purchase_order = self.env['purchase.order'].create(purchase_vals)

        # Actualizar alerta
        self.write({
            'purchase_order_id': purchase_order.id,
            'purchase_order_ids': [(4, purchase_order.id)],
            'state': 'purchase_created',
        })

        # Notificar a compras
        self.message_post(
            body=_('Orden de compra %s creada desde esta alerta.') % purchase_order.name,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Compra'),
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_send_to_multiple_vendors(self):
        """Abrir wizard para enviar cotización a múltiples proveedores."""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('Solo se pueden crear cotizaciones desde alertas pendientes.'))
        
        # Si no hay productos definidos, permitir crear cotización manual desde las notas
        if not self.alert_line_ids and not self.product_id:
            # Abrir wizard de creación manual de cotización
            return {
                'type': 'ir.actions.act_window',
                'name': _('Crear Cotización Manual'),
                'res_model': 'purchase.alert.manual.quotation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_alert_id': self.id,
                },
            }
        
        # Si hay productos, usar el wizard normal
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar Cotización a Múltiples Proveedores'),
            'res_model': 'purchase.quotation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_alert_id': self.id,
            },
        }

    def action_mark_sent(self):
        """Marcar como orden enviada cuando se confirma la orden de compra."""
        self.ensure_one()
        if self.state not in ('purchase_created', 'pending'):
            raise UserError(_('Solo se pueden marcar como orden enviada alertas con cotización solicitada o pendiente.'))
        
        self.write({'state': 'sent'})
        self.message_post(body=_('Orden de compra enviada al proveedor.'))

    def action_cancel(self):
        """Cancelar la alerta."""
        self.ensure_one()
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Alerta cancelada.'))
    
    def _create_approval_activity_for_alert(self, orders, action_type='approved'):
        """Crear una actividad consolidada por alerta cuando se aprueban/rechazan múltiples cotizaciones."""
        self.ensure_one()
        
        # Obtener todas las cotizaciones de la alerta
        all_orders = self.purchase_order_ids
        
        # Contar aprobadas y rechazadas
        approved_orders = all_orders.filtered(lambda o: o.approved_by_crm)
        rejected_orders = all_orders.filtered(lambda o: o.rejected_by_crm)
        approved_count = len(approved_orders)
        rejected_count = len(rejected_orders)
        total_count = len(all_orders)
        
        # Obtener compradores únicos de TODAS las órdenes aprobadas/rechazadas (no solo las que cambiaron)
        if action_type == 'approved':
            orders_for_buyers = approved_orders
        else:
            orders_for_buyers = rejected_orders
        
        buyers = orders_for_buyers.mapped('user_id').filtered(lambda u: u)
        
        if not buyers:
            _logger.warning("No se puede crear actividad para alerta %s: no hay compradores en las órdenes", self.name)
            return
        
        # Determinar mensaje según el estado
        if action_type == 'approved':
            if approved_count == total_count:
                summary = _('✅ Todas las cotizaciones fueron aprobadas por CRM')
                note_content = _('''
                    <p><strong>✅ Todas las cotizaciones fueron aprobadas</strong></p>
                    <p>El área de CRM ha aprobado todas las cotizaciones relacionadas con la alerta <strong>%s</strong>.</p>
                    <p><strong>Total de cotizaciones aprobadas:</strong> %s</p>
                    <p><strong>Cotizaciones aprobadas:</strong></p>
                    <ul>
                ''') % (self.name, approved_count)
                
                for order in all_orders.filtered(lambda o: o.approved_by_crm):
                    note_content += _('<li><strong>%s</strong> - Proveedor: %s%s</li>') % (
                        order.name,
                        order.partner_id.display_name,
                        _(' (Comprador: %s)') % order.user_id.name if order.user_id else ''
                    )
                
                note_content += '</ul>'
                
                # Agregar notas de aprobación si existen
                approval_notes_list = all_orders.filtered(lambda o: o.approved_by_crm and o.approval_notes).mapped('approval_notes')
                if approval_notes_list:
                    unique_notes = list(set(approval_notes_list))
                    note_content += _('<p><strong>Notas de aprobación:</strong></p><ul>')
                    for note in unique_notes:
                        note_content += _('<li>%s</li>') % note
                    note_content += '</ul>'
            else:
                summary = _('✅ Cotizaciones aprobadas por CRM')
                note_content = _('''
                    <p><strong>✅ Cotizaciones aprobadas</strong></p>
                    <p>El área de CRM ha aprobado %s cotización(es) relacionada(s) con la alerta <strong>%s</strong>:</p>
                    <p><strong>Cotizaciones aprobadas:</strong></p>
                    <ul>
                ''') % (len(orders.filtered(lambda o: o.approved_by_crm)), self.name)
                
                for order in orders.filtered(lambda o: o.approved_by_crm):
                    note_content += _('<li><strong>%s</strong> - Proveedor: %s%s</li>') % (
                        order.name,
                        order.partner_id.display_name,
                        _(' (Comprador: %s)') % order.user_id.name if order.user_id else ''
                    )
                
                note_content += '</ul>'
                note_content += _('<p><strong>Estado de todas las cotizaciones:</strong></p><ul>')
                note_content += _('<li>Aprobadas: %s de %s</li>') % (approved_count, total_count)
                note_content += _('<li>Rechazadas: %s de %s</li>') % (rejected_count, total_count)
                note_content += '</ul>'
        
        elif action_type == 'rejected':
            if rejected_count == total_count:
                summary = _('❌ Todas las cotizaciones fueron rechazadas por CRM')
                note_content = _('''
                    <p><strong>❌ Todas las cotizaciones fueron rechazadas</strong></p>
                    <p>El área de CRM ha rechazado todas las cotizaciones relacionadas con la alerta <strong>%s</strong>.</p>
                    <p><strong>Total de cotizaciones rechazadas:</strong> %s</p>
                    <p><strong>Cotizaciones rechazadas:</strong></p>
                    <ul>
                ''') % (self.name, rejected_count)
                
                for order in all_orders.filtered(lambda o: o.rejected_by_crm):
                    note_content += _('<li><strong>%s</strong> - Proveedor: %s%s</li>') % (
                        order.name,
                        order.partner_id.display_name,
                        _(' (Comprador: %s)') % order.user_id.name if order.user_id else ''
                    )
                
                note_content += '</ul>'
                
                # Agregar notas de rechazo si existen
                rejection_notes_list = all_orders.filtered(lambda o: o.rejected_by_crm and o.rejection_notes).mapped('rejection_notes')
                if rejection_notes_list:
                    unique_notes = list(set(rejection_notes_list))
                    note_content += _('<p><strong>Notas de rechazo:</strong></p><ul>')
                    for note in unique_notes:
                        note_content += _('<li>%s</li>') % note
                    note_content += '</ul>'
            else:
                summary = _('❌ Cotizaciones rechazadas por CRM')
                note_content = _('''
                    <p><strong>❌ Cotizaciones rechazadas</strong></p>
                    <p>El área de CRM ha rechazado %s cotización(es) relacionada(s) con la alerta <strong>%s</strong>:</p>
                    <p><strong>Cotizaciones rechazadas:</strong></p>
                    <ul>
                ''') % (len(orders.filtered(lambda o: o.rejected_by_crm)), self.name)
                
                for order in orders.filtered(lambda o: o.rejected_by_crm):
                    note_content += _('<li><strong>%s</strong> - Proveedor: %s%s</li>') % (
                        order.name,
                        order.partner_id.display_name,
                        _(' (Comprador: %s)') % order.user_id.name if order.user_id else ''
                    )
                
                note_content += '</ul>'
                note_content += _('<p><strong>Estado de todas las cotizaciones:</strong></p><ul>')
                note_content += _('<li>Aprobadas: %s de %s</li>') % (approved_count, total_count)
                note_content += _('<li>Rechazadas: %s de %s</li>') % (rejected_count, total_count)
                note_content += '</ul>'
        
        # Verificar si ya existe una actividad reciente similar para evitar duplicados
        # Buscar actividades creadas en los últimos 5 minutos con el mismo resumen
        five_minutes_ago = fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(minutes=5)
        recent_activities = self.env['mail.activity'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'purchase.alert'),
            ('summary', '=', summary),
            ('create_date', '>=', fields.Datetime.to_string(five_minutes_ago)),
        ])
        
        if recent_activities:
            _logger.info("Ya existe una actividad reciente para alerta %s con resumen '%s'. No se creará duplicado.", 
                        self.name, summary)
            return
        
        # Crear una actividad por cada comprador único
        activity_type = self.env['mail.activity.type'].search([
            ('name', 'ilike', 'aprobar' if action_type == 'approved' else 'rechazar'),
            ('res_model', '=', 'purchase.alert'),
        ], limit=1)
        
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([
                ('res_model', '=', 'purchase.alert'),
            ], limit=1)
        
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([
                ('name', '=', 'To Do'),
            ], limit=1)
        
        # Crear actividad para cada comprador único
        for buyer in buyers:
            try:
                activity_vals = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model']._get_id('purchase.alert'),
                    'activity_type_id': activity_type.id if activity_type else False,
                    'summary': summary,
                    'note': note_content,
                    'user_id': buyer.id,
                    'date_deadline': fields.Date.today(),
                }
                
                activity = self.env['mail.activity'].create(activity_vals)
                _logger.info("Actividad consolidada creada para alerta %s, comprador %s: ID=%s", 
                           self.name, buyer.name, activity.id)
            except Exception as e:
                _logger.error("Error creando actividad consolidada para alerta %s, comprador %s: %s", 
                            self.name, buyer.name, str(e), exc_info=True)
        
        # Agregar mensaje en la alerta
        if action_type == 'approved':
            self.message_post(
                body=_('✅ Actividades de notificación creadas para los compradores sobre la aprobación de cotizaciones.'),
            )
        else:
            self.message_post(
                body=_('❌ Actividades de notificación creadas para los compradores sobre el rechazo de cotizaciones.'),
            )

