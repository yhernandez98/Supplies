# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    """Extender Purchase Order para vincular con ventas y clientes."""
    _inherit = 'purchase.order'

    # Modificar el campo partner_id para filtrar solo proveedores
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        change_default=True,
        tracking=True,
        domain="[('tipo_contacto', 'in', ['proveedor', 'ambos'])]",
        help="You can find a vendor by its Name, TIN, Email or Reference.",
    )

    is_leasing = fields.Boolean(
        string='Es Leasing',
        default=False,
        tracking=True,
        help='Indica si esta orden de compra es para productos de leasing'
    )
    leasing_brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca de Leasing',
        tracking=True,
        help='Marca de leasing (ej: HP, Dell). Se puede seleccionar sin necesidad de tener un contrato creado.'
    )
    leasing_contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato de Leasing',
        tracking=True,
        domain="leasing_brand_id and [('brand_ids', 'in', [leasing_brand_id])] or []",
        help='Contrato de leasing relacionado con esta orden de compra. Opcional: primero se puede cotizar con la marca, luego crear el contrato.'
    )
    sale_order_ids = fields.Many2many(
        'sale.order',
        'purchase_sale_order_rel',
        'purchase_id',
        'sale_id',
        string='Órdenes de Venta Relacionadas',
        readonly=True,
        help='Órdenes de venta para las cuales se está comprando este producto',
    )
    sale_order_count = fields.Integer(
        string='Número de Órdenes de Venta',
        compute='_compute_sale_order_count',
        readonly=True,
    )
    partner_customer_ids = fields.Many2many(
        'res.partner',
        'purchase_customer_rel',
        'purchase_id',
        'customer_id',
        string='Clientes Relacionados',
        compute='_compute_partner_customer_ids',
        readonly=True,
        store=False,
        help='Clientes para los cuales se está comprando este producto',
    )
    customer_name = fields.Char(
        string='Cliente Principal',
        compute='_compute_customer_name',
        readonly=True,
        store=False,
        help='Nombre del cliente principal (si solo hay uno)',
    )
    purchase_alert_ids = fields.One2many(
        'purchase.alert',
        'purchase_order_id',
        string='Alertas Por Cotización',
        readonly=True,
    )
    purchase_alert_count = fields.Integer(
        string='Número de Alertas',
        compute='_compute_purchase_alert_count',
        readonly=True,
    )
    approved_by_crm = fields.Boolean(
        string='Aprobada por CRM',
        default=False,
        tracking=True,
        help='Indica si esta cotización ha sido aprobada por el jefe de CRM para proceder con la compra',
    )
    approved_by_crm_user_id = fields.Many2one(
        'res.users',
        string='Aprobada por',
        readonly=True,
        tracking=True,
        help='Usuario de CRM que aprobó esta cotización',
    )
    approved_by_crm_date = fields.Datetime(
        string='Fecha de Aprobación',
        readonly=True,
        tracking=True,
        help='Fecha en que fue aprobada por CRM',
    )
    approval_notes = fields.Text(
        string='Notas de Aprobación',
        help='Notas del jefe de CRM sobre la aprobación de esta cotización',
    )
    rejected_by_crm = fields.Boolean(
        string='Rechazada por CRM',
        default=False,
        tracking=True,
        help='Indica si esta cotización ha sido rechazada por el jefe de CRM',
    )
    rejected_by_crm_user_id = fields.Many2one(
        'res.users',
        string='Rechazada por',
        readonly=True,
        tracking=True,
        help='Usuario de CRM que rechazó esta cotización',
    )
    rejected_by_crm_date = fields.Datetime(
        string='Fecha de Rechazo',
        readonly=True,
        tracking=True,
        help='Fecha en que fue rechazada por CRM',
    )
    rejection_notes = fields.Text(
        string='Notas de Rechazo',
        help='Notas del jefe de CRM sobre el rechazo de esta cotización',
    )
    purchase_alert_references = fields.Char(
        string='Referencias de Alertas',
        compute='_compute_purchase_alert_references',
        readonly=True,
        help='Referencias de las alertas relacionadas con esta orden de compra',
    )
    is_alert_validated = fields.Boolean(
        string='Alerta Validada',
        compute='_compute_is_alert_validated',
        readonly=True,
        store=False,
        help='Indica si alguna de las alertas relacionadas está validada por CRM',
    )
    crm_validation_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ], string='Estado Validación CRM',
        compute='_compute_crm_validation_status',
        readonly=True,
        store=False,
        help='Estado de validación por CRM de esta cotización',
    )
    
    @api.depends('purchase_alert_ids.validated_by_crm')
    def _compute_is_alert_validated(self):
        """Calcular si alguna alerta relacionada está validada."""
        for order in self:
            if not order.id:
                order.is_alert_validated = False
                continue
            # Buscar alertas relacionadas a través de purchase_order_ids (Many2many)
            alerts = self.env['purchase.alert'].search([
                ('purchase_order_ids', 'in', [order.id]),
                ('validated_by_crm', '=', True),
            ], limit=1)
            order.is_alert_validated = bool(alerts)
    
    @api.depends('approved_by_crm', 'rejected_by_crm', 'is_alert_validated')
    def _compute_crm_validation_status(self):
        """Calcular el estado de validación CRM."""
        for order in self:
            if order.approved_by_crm:
                order.crm_validation_status = 'approved'
            elif order.rejected_by_crm:
                order.crm_validation_status = 'rejected'
            else:
                order.crm_validation_status = 'pending'
    
    state_display = fields.Char(
        string='Estado',
        compute='_compute_state_display',
        readonly=True,
        store=False,
        help='Estado combinado que incluye el estado normal y la validación CRM',
    )
    
    @api.depends('state', 'crm_validation_status', 'is_alert_validated', 'approved_by_crm', 'rejected_by_crm', 'purchase_alert_references')
    def _compute_state_display(self):
        """Calcular el estado de validación CRM para mostrar en la lista."""
        for order in self:
            # Solo mostrar si hay una alerta relacionada
            if not order.purchase_alert_references:
                order.state_display = ''
                continue
            
            # Si la alerta está validada, mostrar el estado de validación
            if order.is_alert_validated:
                if order.approved_by_crm:
                    order.state_display = 'Aprobada'
                elif order.rejected_by_crm:
                    order.state_display = 'Rechazada'
                else:
                    order.state_display = 'Pendiente'
            else:
                # Si hay alerta pero no está validada, mostrar pendiente
                order.state_display = 'Pendiente Validación'

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        """Calcular número de órdenes de venta relacionadas."""
        for order in self:
            order.sale_order_count = len(order.sale_order_ids)

    def _compute_has_sale_order(self):
        """Asegurar que has_sale_order tenga siempre un valor (evita ValueError en web_read)."""
        for order in self:
            order.has_sale_order = bool(order.sale_order_ids)

    @api.depends('sale_order_ids.partner_id')
    def _compute_partner_customer_ids(self):
        """Obtener clientes relacionados a través de órdenes de venta."""
        for order in self:
            customers = order.sale_order_ids.mapped('partner_id')
            order.partner_customer_ids = customers

    @api.depends('partner_customer_ids')
    def _compute_customer_name(self):
        """Obtener nombre del cliente principal."""
        for order in self:
            if len(order.partner_customer_ids) == 1:
                order.customer_name = order.partner_customer_ids.display_name
            elif len(order.partner_customer_ids) > 1:
                order.customer_name = _('%s y %s más') % (
                    order.partner_customer_ids[0].display_name,
                    len(order.partner_customer_ids) - 1,
                )
            else:
                order.customer_name = ''

    def action_view_sale_orders(self):
        """Ver órdenes de venta relacionadas."""
        self.ensure_one()
        action = {
            'name': _('Órdenes de Venta'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
        }
        if len(self.sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.sale_order_ids.id,
            })
        return action
    
    def action_view_purchase_alerts(self):
        """Ver alertas relacionadas con esta orden de compra."""
        self.ensure_one()
        action = {
            'name': _('Alertas Por Cotización'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.alert',
            'view_mode': 'list,form',
            'domain': [('purchase_order_ids', 'in', [self.id])],
            'context': {'default_purchase_order_ids': [(4, self.id)]},
        }
        alerts = self.env['purchase.alert'].search([
            ('purchase_order_ids', 'in', [self.id])
        ])
        if len(alerts) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': alerts.id,
            })
        return action

    def action_create_leasing_contract(self):
        """Abrir wizard para crear contrato de leasing desde la orden de compra."""
        self.ensure_one()
        
        return {
            'name': _('Crear Contrato de Leasing'),
            'type': 'ir.actions.act_window',
            'res_model': 'leasing.contract.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
            }
        }
    
    def action_view_leasing_contract(self):
        """Ver el contrato de leasing asociado."""
        self.ensure_one()
        if not self.leasing_contract_id:
            raise UserError(_('No hay contrato de leasing asociado a esta orden de compra.'))
        
        return {
            'name': _('Contrato de Leasing'),
            'type': 'ir.actions.act_window',
            'res_model': 'leasing.contract',
            'res_id': self.leasing_contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.onchange('leasing_brand_id')
    def _onchange_leasing_brand_id(self):
        """Limpiar contrato cuando cambia la marca si no está en las marcas del contrato."""
        if self.leasing_brand_id:
            self.is_leasing = True
            # Limpiar contrato si la marca seleccionada no está en las marcas del contrato
            if self.leasing_contract_id:
                if self.leasing_brand_id.id not in self.leasing_contract_id.brand_ids.ids:
                    self.leasing_contract_id = False
            # Retornar dominio dinámico para filtrar contratos
            domain = []
            if self.leasing_brand_id:
                domain = [('brand_ids', 'in', [self.leasing_brand_id.id])]
            return {'domain': {'leasing_contract_id': domain}}

    @api.onchange('is_leasing')
    def _onchange_is_leasing(self):
        """Limpiar campos de leasing si se desmarca."""
        if not self.is_leasing:
            self.leasing_brand_id = False
            self.leasing_contract_id = False

    @api.depends()
    def _compute_purchase_alert_count(self):
        """Calcular número de alertas relacionadas."""
        for order in self:
            if order.id:
                alerts = self.env['purchase.alert'].search_count([
                    ('purchase_order_ids', 'in', [order.id])
                ])
                order.purchase_alert_count = alerts
            else:
                order.purchase_alert_count = 0

    @api.depends()
    def _compute_purchase_alert_references(self):
        """Calcular referencias de alertas relacionadas."""
        for order in self:
            if order.id:
                alerts = self.env['purchase.alert'].search([
                    ('purchase_order_ids', 'in', [order.id])
                ])
                if alerts:
                    references = ', '.join(alerts.mapped('name'))
                    order.purchase_alert_references = references
                else:
                    order.purchase_alert_references = ''
            else:
                order.purchase_alert_references = ''

    def _update_name_prefix(self, prefix='COT'):
        """Actualizar el prefijo del nombre de la orden."""
        if not self.name:
            return
        
        # Si ya tiene el prefijo correcto, no hacer nada
        if self.name.startswith(prefix):
            return
        
        # Buscar el primer carácter que no es letra (donde termina el prefijo actual)
        match = re.match(r'^([A-Z]+)', self.name)
        if match:
            current_prefix = match.group(1)
            # Reemplazar el prefijo actual con el nuevo
            new_name = self.name.replace(current_prefix, prefix, 1)
            self.name = new_name
        else:
            # Si no tiene prefijo de letras, agregar el prefijo al inicio
            self.name = prefix + self.name

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir creación para generar nombre con prefijo COT cuando está en draft/sent."""
        orders = super().create(vals_list)
        
        for order in orders:
            # Si la orden está en draft o sent, cambiar el prefijo a COT
            if order.state in ('draft', 'sent') and order.name:
                order._update_name_prefix('COT')
        
        return orders

    def write(self, vals):
        """Sobrescribir write para cambiar nombre cuando cambia el estado y actualizar aprobación/rechazo."""
        
        # Prevenir cambios en aprobación/rechazo si la alerta está validada
        for order in self:
            if order.is_alert_validated:
                if 'approved_by_crm' in vals and vals.get('approved_by_crm') != order.approved_by_crm:
                    raise UserError(_('No se puede cambiar el estado de aprobación/rechazo cuando la alerta está validada por CRM.'))
                if 'rejected_by_crm' in vals and vals.get('rejected_by_crm') != order.rejected_by_crm:
                    raise UserError(_('No se puede cambiar el estado de aprobación/rechazo cuando la alerta está validada por CRM.'))
        
        # Prevenir cambios en órdenes rechazadas cuando la alerta está validada
        for order in self:
            if order.is_alert_validated and order.rejected_by_crm:
                # Permitir solo cambios en campos específicos que no afecten la orden
                allowed_fields = {'message_follower_ids', 'activity_ids', 'message_ids', 'activity_date_deadline'}
                restricted_fields = set(vals.keys()) - allowed_fields
                if restricted_fields:
                    raise UserError(_('No se puede modificar una cotización rechazada cuando la alerta está validada por CRM. Esta cotización ha sido rechazada y está bloqueada.'))
        
        # Si se marca como aprobada, limpiar rechazo
        if 'approved_by_crm' in vals and vals.get('approved_by_crm'):
            vals['rejected_by_crm'] = False
            vals['rejected_by_crm_user_id'] = False
            vals['rejected_by_crm_date'] = False
            vals['rejection_notes'] = False
        
        # Si se marca como rechazada, limpiar aprobación
        if 'rejected_by_crm' in vals and vals.get('rejected_by_crm'):
            vals['approved_by_crm'] = False
            vals['approved_by_crm_user_id'] = False
            vals['approved_by_crm_date'] = False
            vals['approval_notes'] = False
        
        # Si se desmarca aprobación, limpiar campos
        if 'approved_by_crm' in vals and not vals.get('approved_by_crm'):
            vals['approved_by_crm_user_id'] = False
            vals['approved_by_crm_date'] = False
            vals['approval_notes'] = False
        
        # Si se desmarca rechazo, limpiar campos
        if 'rejected_by_crm' in vals and not vals.get('rejected_by_crm'):
            vals['rejected_by_crm_user_id'] = False
            vals['rejected_by_crm_date'] = False
            vals['rejection_notes'] = False
        
        # Detectar cambios ANTES de escribir para saber qué órdenes necesitan actividades
        orders_to_notify_approval = []
        orders_to_notify_rejection = []
        
        if 'approved_by_crm' in vals:
            will_be_approved = vals.get('approved_by_crm', False)
            for po in self:
                was_approved_before = po.approved_by_crm
                # Si está cambiando de False a True, necesita actividad
                if will_be_approved and not was_approved_before:
                    orders_to_notify_approval.append(po.id)
        
        if 'rejected_by_crm' in vals:
            will_be_rejected = vals.get('rejected_by_crm', False)
            for po in self:
                was_rejected_before = po.rejected_by_crm
                # Si está cambiando de False a True, necesita actividad
                if will_be_rejected and not was_rejected_before:
                    orders_to_notify_rejection.append(po.id)
        
        # Actualizar campos de aprobación/rechazo en vals si hay órdenes que cambiarán
        if orders_to_notify_approval and 'approved_by_crm_user_id' not in vals:
            vals['approved_by_crm_user_id'] = self.env.user.id
        if orders_to_notify_approval and 'approved_by_crm_date' not in vals:
            vals['approved_by_crm_date'] = fields.Datetime.now()
        
        if orders_to_notify_rejection and 'rejected_by_crm_user_id' not in vals:
            vals['rejected_by_crm_user_id'] = self.env.user.id
        if orders_to_notify_rejection and 'rejected_by_crm_date' not in vals:
            vals['rejected_by_crm_date'] = fields.Datetime.now()
        
        # Detectar si el estado está cambiando
        state_changes = {}
        if 'state' in vals:
            for order in self:
                old_state = order.state
                new_state = vals['state']
                if old_state != new_state:
                    state_changes[order.id] = (old_state, new_state)
        
        result = super().write(vals)
        
        # Después de escribir, crear actividades agrupadas por alerta SOLO cuando se aprueba
        if orders_to_notify_approval:
            _logger.info("Se detectaron %s órdenes para crear actividad de aprobación: %s", 
                        len(orders_to_notify_approval), orders_to_notify_approval)
            orders = self.env['purchase.order'].browse(orders_to_notify_approval)
            # Agrupar órdenes por alerta y crear una actividad por alerta
            self.env['purchase.order']._create_approval_activities_grouped(orders)
        
        # Después de escribir, actualizar nombres según el cambio de estado
        if 'state' in vals:
            for order in self:
                if order.id in state_changes:
                    old_state, new_state = state_changes[order.id]
                    # Si pasa de draft/sent a purchase, cambiar COT a COM
                    if old_state in ('draft', 'sent') and new_state == 'purchase':
                        order._update_name_prefix('COM')
                    # Si pasa de purchase a draft/sent, cambiar COM a COT
                    elif old_state == 'purchase' and new_state in ('draft', 'sent'):
                        order._update_name_prefix('COT')
        
        return result
    
    @api.model
    def _create_approval_activities_grouped(self, orders):
        """Crear actividades agrupadas por alerta cuando se aprueban múltiples cotizaciones."""
        if not orders:
            return
        
        # Agrupar órdenes por alerta
        alerts_dict = {}  # {alert_id: [order_ids]}
        
        for order in orders:
            # Buscar alertas relacionadas
            alerts = self.env['purchase.alert'].search([
                ('purchase_order_ids', 'in', [order.id])
            ])
            
            for alert in alerts:
                if alert.id not in alerts_dict:
                    alerts_dict[alert.id] = []
                alerts_dict[alert.id].append(order.id)
        
        # Crear una actividad por cada alerta
        for alert_id, order_ids in alerts_dict.items():
            try:
                alert = self.env['purchase.alert'].browse(alert_id)
                if not alert.exists():
                    continue
                
                orders_in_alert = self.env['purchase.order'].browse(order_ids)
                alert._create_approval_activity_for_alert(orders_in_alert, 'approved')
            except Exception as e:
                _logger.error("Error creando actividad agrupada de aprobación para alerta %s: %s", alert_id, str(e), exc_info=True)
    
    @api.model
    def _create_rejection_activities_grouped(self, orders):
        """Crear actividades agrupadas por alerta cuando se rechazan múltiples cotizaciones."""
        if not orders:
            return
        
        # Agrupar órdenes por alerta
        alerts_dict = {}  # {alert_id: [order_ids]}
        
        for order in orders:
            # Buscar alertas relacionadas
            alerts = self.env['purchase.alert'].search([
                ('purchase_order_ids', 'in', [order.id])
            ])
            
            for alert in alerts:
                if alert.id not in alerts_dict:
                    alerts_dict[alert.id] = []
                alerts_dict[alert.id].append(order.id)
        
        # Crear una actividad por cada alerta
        for alert_id, order_ids in alerts_dict.items():
            try:
                alert = self.env['purchase.alert'].browse(alert_id)
                if not alert.exists():
                    continue
                
                orders_in_alert = self.env['purchase.order'].browse(order_ids)
                alert._create_approval_activity_for_alert(orders_in_alert, 'rejected')
            except Exception as e:
                _logger.error("Error creando actividad agrupada de rechazo para alerta %s: %s", alert_id, str(e), exc_info=True)
    
    def button_confirm(self):
        """Sobrescribir confirmación para actualizar estado de alertas y cambiar nombre a COM."""
        # Prevenir confirmación de órdenes rechazadas cuando la alerta está validada
        for order in self:
            if order.is_alert_validated and order.rejected_by_crm:
                raise UserError(_('No se puede confirmar una cotización rechazada cuando la alerta está validada por CRM. Esta cotización ha sido rechazada y está bloqueada.'))
        
        # Cambiar nombre antes de confirmar
        for order in self:
            if order.state in ('draft', 'sent'):
                order._update_name_prefix('COM')
        
        result = super().button_confirm()
        
        # Actualizar estado de alertas relacionadas a "Orden Enviada" cuando se confirma la orden
        for order in self:
            # Buscar alertas relacionadas a través de purchase_order_ids (many2many)
            alerts = self.env['purchase.alert'].search([
                ('purchase_order_ids', 'in', [order.id]),
                ('state', 'in', ('pending', 'purchase_created')),
            ])
            if alerts:
                alerts.write({'state': 'sent'})
                for alert in alerts:
                    alert.message_post(
                        body=_('Orden de compra %s confirmada. Alerta marcada como Orden Enviada.') % order.name
                    )
        
        return result
    

