# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class SaleOrderRequestQuotationWizard(models.TransientModel):
    """Wizard para solicitar cotización de compra desde orden de venta sin productos."""
    _name = 'sale.order.request.quotation.wizard'
    _description = 'Wizard para Solicitar Cotización de Compra desde Orden de Venta'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='sale_order_id.partner_id',
        readonly=True,
        store=False,
    )
    opportunity_id = fields.Many2one(
        'crm.lead',
        string='Oportunidad',
        related='sale_order_id.opportunity_id',
        readonly=True,
        store=False,
    )
    notes = fields.Text(
        string='Descripción de lo que se necesita cotizar',
        required=False,
        help='Describe los productos o servicios que necesita cotizar el área de compras. Esta información aparecerá en la alerta. Solo requerido si no hay productos en la orden.',
    )
    has_products_needing_stock = fields.Boolean(
        string='Tiene Productos Sin Stock',
        compute='_compute_has_products_needing_stock',
        readonly=True,
        store=False,
        help='Indica si la orden tiene productos que necesitan stock',
    )
    
    @api.depends('sale_order_id')
    def _compute_has_products_needing_stock(self):
        """Calcular si hay productos que necesitan stock."""
        for wizard in self:
            if not wizard.sale_order_id:
                wizard.has_products_needing_stock = False
                continue
            
            sale_order = wizard.sale_order_id
            if not sale_order.warehouse_id:
                wizard.has_products_needing_stock = False
                continue
            
            # Verificar si hay productos físicos sin stock
            location = sale_order.warehouse_id.lot_stock_id
            has_products = False
            
            for line in sale_order.order_line:
                if not line.product_id:
                    continue
                
                # Verificar tipo de producto
                ptype = None
                if line.product_id.product_tmpl_id:
                    ptype = line.product_id.product_tmpl_id.type
                else:
                    ptype = line.product_id.type
                
                if ptype not in ('product', 'consu'):
                    continue
                
                try:
                    # Verificar stock
                    all_quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                    accessible_quants = self.env['stock.quant']
                    for quant in all_quants:
                        try:
                            quant_check = self.env['stock.quant'].browse(quant.id)
                            if quant_check.exists():
                                accessible_quants |= quant_check
                        except Exception:
                            continue
                    qty_available = sum(accessible_quants.mapped('quantity'))
                    qty_needed = line.product_uom_qty
                    
                    if qty_available < qty_needed:
                        has_products = True
                        break
                except Exception:
                    continue
            
            wizard.has_products_needing_stock = has_products
    assign_to_user_id = fields.Many2one(
        'res.users',
        string='Asignar a',
        required=True,
        domain=lambda self: self._get_purchase_users_domain(),
        help='Usuario del área de compras que debe realizar la cotización',
    )
    
    @api.model
    def _get_purchase_users_domain(self):
        """Obtener dominio para filtrar usuarios de compras."""
        purchase_group = self.env.ref('purchase.group_purchase_user', raise_if_not_found=False)
        if purchase_group:
            return [('groups_id', 'in', [purchase_group.id])]
        return []
    activity_type_id = fields.Many2one(
        'mail.activity.type',
        string='Tipo de Actividad',
        default=lambda self: self._default_activity_type(),
        help='Tipo de actividad a crear',
    )
    activity_summary = fields.Char(
        string='Resumen de la Actividad',
        default='Cotizar productos/servicios solicitados',
        required=True,
        help='Título de la actividad',
    )
    activity_date_deadline = fields.Date(
        string='Fecha Límite',
        default=lambda self: fields.Date.today() + timedelta(days=3),
        required=True,
        help='Fecha límite para completar la actividad',
    )
    activity_note = fields.Html(
        string='Notas de la Actividad',
        help='Notas adicionales para la actividad',
    )

    @api.model
    def _default_activity_type(self):
        """Obtener tipo de actividad por defecto para compras."""
        activity_type = self.env['mail.activity.type'].search([
            ('name', 'ilike', 'cotizar'),
            ('res_model', '=', 'purchase.alert'),
        ], limit=1)
        if not activity_type:
            # Buscar tipo genérico
            activity_type = self.env['mail.activity.type'].search([
                ('res_model', '=', 'purchase.alert'),
            ], limit=1)
        if not activity_type:
            # Usar tipo "To Do" genérico
            activity_type = self.env['mail.activity.type'].search([
                ('name', '=', 'To Do'),
            ], limit=1)
        return activity_type.id if activity_type else False

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto."""
        res = super().default_get(fields_list)
        
        # Obtener sale_order_id del contexto
        sale_order_id = self.env.context.get('active_id') or self.env.context.get('default_sale_order_id')
        active_model = self.env.context.get('active_model')
        
        # Recopilar descripción de notas y secciones de la orden
        description_text = ''
        
        if active_model == 'sale.order' and sale_order_id:
            sale_order = self.env['sale.order'].browse(sale_order_id)
            if sale_order.exists():
                res['sale_order_id'] = sale_order.id
                
                # Obtener todas las notas y secciones de las líneas de la orden
                notes_sections = []
                for line in sale_order.order_line:
                    if line.display_type in ('line_section', 'line_note'):
                        if line.name:
                            notes_sections.append(line.name.strip())
                
                # Si hay notas/secciones, usarlas como descripción
                if notes_sections:
                    description_text = '\n\n'.join(notes_sections)
                    res['notes'] = description_text
                
                # Si no hay notas/secciones, intentar usar otros campos
                if not description_text:
                    if sale_order.note:
                        res['notes'] = sale_order.note
                        description_text = sale_order.note
                    elif sale_order.opportunity_id and sale_order.opportunity_id.description:
                        res['notes'] = sale_order.opportunity_id.description
                        description_text = sale_order.opportunity_id.description
        
        # Establecer notas de actividad con la descripción recopilada
        if sale_order_id and 'activity_note' in fields_list:
            sale_order = self.env['sale.order'].browse(sale_order_id)
            if sale_order.exists():
                # Usar la descripción de notas/secciones como contenido principal
                if description_text:
                    # Convertir texto simple a HTML preservando saltos de línea
                    activity_content = description_text.replace('\n', '<br/>')
                    res['activity_note'] = '<p>%s</p>' % activity_content
                else:
                    # Fallback si no hay notas/secciones
                    note_parts = []
                    note_parts.append(_('<p><strong>Cliente:</strong> %s</p>') % (
                        sale_order.partner_id.display_name if sale_order.partner_id else 'N/A'
                    ))
                    if sale_order.opportunity_id:
                        note_parts.append(_('<p><strong>Oportunidad:</strong> %s</p>') % sale_order.opportunity_id.name)
                    note_parts.append(_('<p><strong>Orden de Venta:</strong> %s</p>') % sale_order.name)
                    if sale_order.validity_date:
                        note_parts.append(_('<p><strong>Vencimiento de Cotización:</strong> %s</p>') % sale_order.validity_date.strftime('%d/%m/%Y'))
                    res['activity_note'] = ''.join(note_parts)
        
        return res

    def action_create_alert_and_activity(self):
        """Crear alerta y asignar actividad a compras."""
        self.ensure_one()
        
        if not self.assign_to_user_id:
            raise UserError(_('Debe seleccionar un usuario del área de compras para asignar la actividad.'))
        
        sale_order = self.sale_order_id
        
        # Obtener almacén
        warehouse = sale_order.warehouse_id or self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            raise UserError(_('No se encontró ningún almacén configurado. Configure un almacén antes de crear alertas.'))
        
        # Obtener Lead/Oportunidad
        lead = sale_order.opportunity_id
        if not lead:
            raise UserError(_('La orden de venta debe estar vinculada a una oportunidad (Lead) para crear una alerta.'))
        
        # Verificar si hay productos sin stock
        if self.has_products_needing_stock:
            # CASO 1: Hay productos sin stock - crear alerta con productos usando método automático
            _logger.info("Orden %s tiene productos sin stock - Creando alerta automática con productos", sale_order.name)
            
            # Usar el método automático para crear alertas con productos
            # Pero con contexto para prevenir duplicados
            sale_order.with_context(
                skip_auto_create_alerts=False,  # Permitir creación automática
                manual_alert_creation=True,  # Pero marcar como manual para evitar duplicados
                from_wizard=True  # Indicar que viene del wizard
            ).sudo()._create_purchase_alerts_automatically()
            
            # Buscar la alerta recién creada
            alert = self.env['purchase.alert'].search([
                ('sale_order_id', '=', sale_order.id),
                ('state', '=', 'pending'),
            ], order='create_date desc', limit=1)
            
            if not alert:
                raise UserError(_('No se pudo crear la alerta. Por favor, verifique que hay productos sin stock en la orden.'))
            
            # Si hay notas adicionales, agregarlas a la alerta
            if self.notes and self.notes.strip():
                existing_notes = alert.notes or ''
                if existing_notes:
                    alert.write({
                        'notes': f"{existing_notes}\n\n--- Notas adicionales ---\n{self.notes}"
                    })
                else:
                    alert.write({
                        'notes': self.notes
                    })
        else:
            # CASO 2: No hay productos sin stock - crear alerta con descripción/notas
            if not self.notes or not self.notes.strip():
                raise UserError(_('Debe especificar una descripción de lo que se necesita cotizar cuando no hay productos en la orden.'))
            
            _logger.info("Orden %s no tiene productos sin stock - Creando alerta manual con descripción", sale_order.name)
            
            # Crear alerta sin productos (solo con notas)
            alert_vals = {
                'sale_order_id': sale_order.id,
                'lead_id': lead.id,
                'partner_id': sale_order.partner_id.id if sale_order.partner_id else False,
                'state': 'pending',
                'warehouse_id': warehouse.id,
                'notes': self.notes,  # Solo las notas del usuario
            }
            
            # Crear la alerta con contexto para prevenir creación automática de alertas
            alert = self.env['purchase.alert'].with_context(
                skip_auto_create_alerts=True,
                manual_alert_creation=True
            ).create(alert_vals)
        
        # Crear actividad asignada al usuario de compras
        activity_vals = {
            'res_id': alert.id,
            'res_model_id': self.env['ir.model']._get_id('purchase.alert'),
            'activity_type_id': self.activity_type_id.id if self.activity_type_id else False,
            'summary': self.activity_summary,
            'note': self.activity_note or '',
            'user_id': self.assign_to_user_id.id,
            'date_deadline': self.activity_date_deadline,
        }
        
        activity = self.env['mail.activity'].create(activity_vals)
        
        # Agregar mensaje en la alerta
        alert.message_post(
            body=_('✅ Alerta creada desde orden de venta %s.\n\n📋 Actividad asignada a: %s\n📅 Fecha límite: %s') % (
                sale_order.name,
                self.assign_to_user_id.name,
                self.activity_date_deadline.strftime('%d/%m/%Y')
            ),
        )
        
        # Agregar mensaje en la orden de venta
        sale_order.message_post(
            body=_('✅ Alerta de cotización %s creada y actividad asignada a %s.') % (
                alert.name,
                self.assign_to_user_id.name
            ),
        )
        
        # Agregar mensaje en el Lead
        if lead:
            lead.message_post(
                body=_('✅ Alerta de cotización %s creada desde orden de venta %s.\n\nActividad asignada a: %s') % (
                    alert.name,
                    sale_order.name,
                    self.assign_to_user_id.name
                ),
            )
        
        _logger.info("Alerta %s creada desde orden %s con actividad asignada a %s", 
                    alert.name, sale_order.name, self.assign_to_user_id.name)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alerta Creada'),
            'res_model': 'purchase.alert',
            'res_id': alert.id,
            'view_mode': 'form',
            'target': 'current',
        }

