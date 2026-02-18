# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    """Extender CRM Lead para verificar stock al cotizar y generar suscripciones."""
    _inherit = 'crm.lead'

    sale_order_ids = fields.One2many(
        'sale.order',
        'opportunity_id',
        string='Órdenes de Venta',
        readonly=True,
    )
    purchase_alert_ids = fields.One2many(
        'purchase.alert',
        'lead_id',
        string='Alertas Por Cotización',
        readonly=True,
    )
    purchase_alert_count = fields.Integer(
        string='Número de Alertas',
        compute='_compute_purchase_alert_count',
        readonly=True,
    )
    subscription_ids = fields.One2many(
        'subscription.subscription',
        compute='_compute_subscription_ids',
        string='Suscripciones Relacionadas',
        readonly=True,
    )
    subscription_count = fields.Integer(
        string='Número de Suscripciones',
        compute='_compute_subscription_count',
        readonly=True,
    )
    is_subscription_opportunity = fields.Boolean(
        string='Es Oportunidad de Suscripción',
        default=False,
        help='Indica si esta oportunidad es para un servicio de suscripción en lugar de una venta',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación del Cliente',
        help='Ubicación donde se instalará el servicio (para suscripciones)',
        domain=[('usage', '=', 'customer')],
    )
    auto_generate_subscription = fields.Boolean(
        string='Generar Suscripción Automáticamente',
        default=False,
        help='Si está activado, al aceptar el cliente se generará automáticamente la suscripción',
    )
    supplies_stock_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_supplies_stock_quants',
        string='Inventario Supp/Existencias',
        compute_sudo=True,
        help='Inventario existente en la ubicación Supp/Existencias.',
    )

    @api.depends('purchase_alert_ids')
    def _compute_purchase_alert_count(self):
        """Calcular número de alertas por cotización."""
        for lead in self:
            lead.purchase_alert_count = len(lead.purchase_alert_ids.filtered(lambda a: a.state == 'pending'))

    @api.depends('partner_id', 'location_id')
    def _compute_subscription_ids(self):
        """Calcular suscripciones relacionadas con este lead."""
        Subscription = self.env['subscription.subscription']
        for lead in self:
            domain = [('partner_id', '=', lead.partner_id.id)] if lead.partner_id else []
            if lead.location_id:
                domain.append(('location_id', '=', lead.location_id.id))
            subscriptions = Subscription.search(domain) if domain else Subscription.browse()
            lead.subscription_ids = subscriptions

    @api.depends('subscription_ids')
    def _compute_subscription_count(self):
        """Calcular número de suscripciones."""
        for lead in self:
            lead.subscription_count = len(lead.subscription_ids)

    @api.depends()
    def _compute_supplies_stock_quants(self):
        """Calcular inventario de la ubicación Supp/Existencias."""
        Quant = self.env['stock.quant'].sudo()
        Location = self.env['stock.location'].sudo()
        
        # Buscar ubicación Supp/Existencias
        supplies_location = Location.search([
            ('complete_name', 'ilike', 'Supp/Existencias'),
            ('usage', '=', 'internal'),
        ], limit=1)
        
        for lead in self:
            if not supplies_location:
                lead.supplies_stock_quant_ids = False
                continue
            
            # Obtener todos los quants con cantidad > 0 en Supp/Existencias
            # Usar sudo() para la búsqueda y luego filtrar solo los accesibles
            try:
                all_quants = Quant.sudo().search([
                    ('location_id', 'child_of', supplies_location.id),
                    ('quantity', '>', 0),
                ])
                
                # Filtrar solo los quants que el usuario actual puede leer
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        # Intentar leer el quant sin sudo para verificar permisos
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        # Si no puede leer el quant, omitirlo
                        continue
                
                lead.supplies_stock_quant_ids = accessible_quants
            except Exception:
                # Si hay error, dejar vacío
                lead.supplies_stock_quant_ids = False

    def action_view_purchase_alerts(self):
        """Ver alertas por cotización relacionadas con este lead."""
        self.ensure_one()
        action = {
            'name': _('Alertas Por Cotización'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.alert',
            'view_mode': 'tree,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }
        if len(self.purchase_alert_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.purchase_alert_ids.id,
            })
        return action

    def action_view_subscriptions(self):
        """Ver suscripciones relacionadas con este lead."""
        self.ensure_one()
        action = {
            'name': _('Suscripciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.subscription',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.subscription_ids.ids)],
        }
        if len(self.subscription_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.subscription_ids.id,
            })
        return action

    def action_generate_subscription(self):
        """Generar suscripción automáticamente desde el Lead."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Debe especificar un cliente para generar la suscripción.'))
        
        if not self.is_subscription_opportunity:
            raise UserError(_('Esta oportunidad no está marcada como suscripción. Active "Es Oportunidad de Suscripción".'))

        # Preparar productos desde cotizaciones
        products = []
        
        # Si hay órdenes de venta, obtener productos de servicios
        if self.sale_order_ids:
            for sale_order in self.sale_order_ids:
                for line in sale_order.order_line:
                    if line.product_id and line.product_id.type == 'service':
                        products.append({
                            'product': line.product_id,
                            'quantity': line.product_uom_qty,
                            'price': line.price_unit,
                        })

        # Obtener ubicación del cliente
        location = self.location_id
        if not location and self.partner_id:
            location = self.partner_id.property_stock_customer

        # Crear o actualizar suscripción usando ensure_subscription
        Subscription = self.env['subscription.subscription']
        subscription = Subscription.ensure_subscription(
            partner=self.partner_id,
            location=location,
            products=products if products else None,
            remove_missing=False,
            track_usage=True,
        )

        # Actualizar estado del lead
        self.write({
            'auto_generate_subscription': True,
        })

        # Mensaje informativo
        self.message_post(
            body=_('✅ Suscripción %s generada automáticamente desde este lead.') % subscription.name,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Suscripción Generada'),
            'res_model': 'subscription.subscription',
            'res_id': subscription.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_accept_and_generate(self):
        """Aceptar oportunidad y generar suscripción automáticamente (si aplica)."""
        self.ensure_one()
        
        # Si está marcado para generar suscripción automáticamente
        if self.is_subscription_opportunity and self.auto_generate_subscription:
            return self.action_generate_subscription()
        else:
            # Si no es suscripción, seguir flujo normal de venta
            return self.action_new_quotation()
    
    def action_request_quotation(self):
        """Solicitar cotización de compra desde el CRM Lead."""
        self.ensure_one()
        
        # Si no hay órdenes de venta, abrir wizard para crear alertas directamente
        if not self.sale_order_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Solicitar Cotización de Compra'),
                'res_model': 'crm.lead.purchase.alert.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_lead_id': self.id},
            }
        
        # Buscar órdenes en estado de cotización (draft o sent)
        quotation_orders = self.sale_order_ids.filtered(
            lambda o: o.state in ('draft', 'sent')
        )
        
        if not quotation_orders:
            raise UserError(_('No hay órdenes en estado de cotización. Todas las órdenes están confirmadas o canceladas.'))
        
        # Obtener alertas existentes antes de crear nuevas
        existing_alert_ids = self.purchase_alert_ids.filtered(lambda a: a.state == 'pending').ids
        
        # Verificar stock y crear alertas automáticamente para cada orden
        for order in quotation_orders:
            # Verificar stock y crear alertas si es necesario
            if order.warehouse_id:
                order._compute_stock_availability()
                order.flush_recordset()
                order.sudo()._create_purchase_alerts_automatically()
        
        # Obtener alertas después de crear
        self.invalidate_recordset(['purchase_alert_ids'])
        new_alert_ids = self.purchase_alert_ids.filtered(lambda a: a.state == 'pending').ids
        alerts_created = [aid for aid in new_alert_ids if aid not in existing_alert_ids]
        
        if alerts_created:
            alerts = self.env['purchase.alert'].browse(alerts_created)
            self.message_post(
                body=_('✅ Se crearon automáticamente %s alerta(s) de cotización de compra.') % len(alerts_created),
            )
            return {
                'type': 'ir.actions.act_window',
                'name': _('Alertas Por Cotización Creadas'),
                'res_model': 'purchase.alert',
                'view_mode': 'list,form',
                'domain': [('id', 'in', alerts_created)],
                'context': {'default_lead_id': self.id},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se crearon alertas nuevas. Todas las órdenes tienen stock disponible o ya tienen alertas pendientes.'),
                    'type': 'info',
                }
            }
    
    def action_request_purchase(self):
        """Solicitar compra desde el CRM Lead (similar a solicitar cotización pero para órdenes confirmadas)."""
        self.ensure_one()
        
        # Si no hay órdenes de venta, abrir wizard para crear alertas directamente
        if not self.sale_order_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Solicitar Compra'),
                'res_model': 'crm.lead.purchase.alert.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_lead_id': self.id},
            }
        
        # Buscar órdenes confirmadas (sale o done)
        confirmed_orders = self.sale_order_ids.filtered(
            lambda o: o.state in ('sale', 'done')
        )
        
        if not confirmed_orders:
            raise UserError(_('No hay órdenes confirmadas. Debe confirmar las órdenes de venta primero.'))
        
        # Obtener alertas existentes antes de crear nuevas
        existing_alert_ids = self.purchase_alert_ids.filtered(lambda a: a.state == 'pending').ids
        
        # Verificar stock y crear alertas automáticamente para cada orden confirmada
        for order in confirmed_orders:
            # Verificar stock y crear alertas si es necesario
            if order.warehouse_id:
                order._compute_stock_availability()
                order.flush_recordset()
                order.sudo()._create_purchase_alerts_automatically()
        
        # Obtener alertas después de crear
        self.invalidate_recordset(['purchase_alert_ids'])
        new_alert_ids = self.purchase_alert_ids.filtered(lambda a: a.state == 'pending').ids
        alerts_created = [aid for aid in new_alert_ids if aid not in existing_alert_ids]
        
        if alerts_created:
            alerts = self.env['purchase.alert'].browse(alerts_created)
            self.message_post(
                body=_('✅ Se crearon automáticamente %s alerta(s) de compra para órdenes confirmadas.') % len(alerts_created),
            )
            return {
                'type': 'ir.actions.act_window',
                'name': _('Alertas Por Cotización Creadas'),
                'res_model': 'purchase.alert',
                'view_mode': 'list,form',
                'domain': [('id', 'in', alerts_created)],
                'context': {'default_lead_id': self.id},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se crearon alertas nuevas. Todas las órdenes tienen stock disponible o ya tienen alertas pendientes.'),
                    'type': 'info',
                }
            }


