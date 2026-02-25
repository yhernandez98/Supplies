# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CrmLeadPurchaseAlertWizard(models.TransientModel):
    """Wizard para crear alertas de compra desde CRM Lead sin necesidad de órdenes de venta."""
    _name = 'crm.lead.purchase.alert.wizard'
    _description = 'Wizard para Crear Alertas de Compra desde CRM Lead'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead/Oportunidad',
        required=True,
        readonly=False,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='lead_id.partner_id',
        readonly=True,
        store=False,
    )
    line_ids = fields.One2many(
        'crm.lead.purchase.alert.wizard.line',
        'wizard_id',
        string='Productos a Solicitar',
    )
    notes = fields.Text(
        string='Notas Adicionales',
        help='Notas adicionales sobre la solicitud de compra',
    )

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto desde el Lead."""
        res = super().default_get(fields_list)
        
        # Intentar obtener el Lead del contexto
        lead_id = self.env.context.get('active_id')
        if not lead_id:
            # Si no hay active_id, intentar obtenerlo desde active_model
            active_model = self.env.context.get('active_model')
            if active_model == 'crm.lead':
                lead_id = self.env.context.get('active_id')
        
        if lead_id and 'lead_id' in fields_list:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead.exists():
                res['lead_id'] = lead.id
                # Si hay órdenes de venta con productos, sugerirlos
                if lead.sale_order_ids:
                    lines = []
                    for order in lead.sale_order_ids:
                        for line in order.order_line:
                            if line.product_id and line.product_id.type in ('product', 'consu'):
                                # Verificar si ya existe en las líneas
                                existing = [l for l in lines if l['product_id'] == line.product_id.id]
                                if existing:
                                    existing[0]['quantity'] += line.product_uom_qty
                                else:
                                    lines.append({
                                        'product_id': line.product_id.id,
                                        'quantity': line.product_uom_qty,
                                        'uom_id': line.product_uom.id,
                                    })
                    res['line_ids'] = [(0, 0, line) for line in lines]
        
        return res

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """Actualizar partner_id y sugerir productos cuando se selecciona un Lead."""
        for wizard in self:
            if wizard.lead_id:
                # Actualizar partner_id
                wizard.partner_id = wizard.lead_id.partner_id
                
                # Si hay órdenes de venta con productos, sugerirlos en las líneas
                if wizard.lead_id.sale_order_ids:
                    lines = []
                    for order in wizard.lead_id.sale_order_ids:
                        for line in order.order_line:
                            if line.product_id and line.product_id.type in ('product', 'consu'):
                                # Verificar si ya existe en las líneas actuales
                                existing = wizard.line_ids.filtered(
                                    lambda l: l.product_id.id == line.product_id.id
                                )
                                if existing:
                                    # Actualizar cantidad si es mayor
                                    if existing[0].quantity < line.product_uom_qty:
                                        existing[0].quantity = line.product_uom_qty
                                else:
                                    # Agregar nueva línea
                                    lines.append((0, 0, {
                                        'product_id': line.product_id.id,
                                        'quantity': line.product_uom_qty,
                                        'uom_id': line.product_uom.id,
                                    }))
                    if lines:
                        wizard.line_ids = lines
            else:
                wizard.partner_id = False

    def action_create_alerts(self):
        """Crear alertas de compra desde el wizard."""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('Debe agregar al menos un producto para crear alertas de compra.'))
        
        if not self.lead_id:
            raise UserError(_('No se encontró el Lead relacionado.'))
        
        lead = self.lead_id
        
        # Obtener almacén por defecto
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            raise UserError(_('No se encontró ningún almacén configurado. Configure un almacén antes de crear alertas.'))
        
        alerts_created = []
        
        for line in self.line_ids:
            if not line.product_id or line.quantity <= 0:
                continue
            
            # Verificar stock disponible
            location = warehouse.lot_stock_id
            try:
                # Usar sudo() para _gather y luego filtrar solo los accesibles
                all_quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                # Filtrar solo los quants que el usuario actual puede leer
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        continue
                qty_available = sum(accessible_quants.mapped('quantity'))
                qty_needed = line.quantity
                
                # Crear alerta solo si falta stock o si el usuario quiere solicitar de todas formas
                # Si hay stock suficiente, también crear alerta si el usuario lo solicita explícitamente
                if qty_available < qty_needed or line.force_create:
                    # Buscar si ya existe una alerta pendiente para este producto y Lead
                    existing_alert = self.env['purchase.alert'].search([
                        ('lead_id', '=', lead.id),
                        ('product_id', '=', line.product_id.id),
                        ('state', '=', 'pending'),
                    ], limit=1)
                    
                    if not existing_alert:
                        # Crear orden de venta temporal si no existe
                        sale_order = None
                        if not lead.sale_order_ids:
                            # Crear una orden de venta temporal en borrador para vincular la alerta
                            sale_order = self.env['sale.order'].create({
                                'partner_id': lead.partner_id.id if lead.partner_id else False,
                                'opportunity_id': lead.id,
                                'state': 'draft',
                                'warehouse_id': warehouse.id,
                            })
                            _logger.info("Orden de venta temporal %s creada para Lead %s", sale_order.name, lead.name)
                        else:
                            # Usar la primera orden de venta existente
                            sale_order = lead.sale_order_ids[0]
                        
                        # Crear alerta
                        alert = self.env['purchase.alert'].create({
                            'lead_id': lead.id,
                            'sale_order_id': sale_order.id,
                            'product_id': line.product_id.id,
                            'quantity_requested': qty_needed,
                            'state': 'pending',
                            'warehouse_id': warehouse.id,
                            'partner_id': lead.partner_id.id if lead.partner_id else False,
                            'notes': self.notes or _('Creado desde CRM Lead: %s') % lead.name,
                        })
                        alerts_created.append(alert)
                        _logger.info("Alerta %s creada para producto %s (Lead: %s)", alert.name, line.product_id.display_name, lead.name)
                    else:
                        # Actualizar cantidad solicitada si es mayor
                        if existing_alert.quantity_requested < qty_needed:
                            existing_alert.write({'quantity_requested': qty_needed})
                            alerts_created.append(existing_alert)
                            _logger.info("Alerta existente %s actualizada (Lead: %s)", existing_alert.name, lead.name)
            except Exception as e:
                _logger.error("Error creando alerta para producto %s: %s", line.product_id.display_name, str(e), exc_info=True)
                # Continuar con el siguiente producto
                continue
        
        if not alerts_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se crearon alertas nuevas. Todos los productos tienen stock suficiente o ya tienen alertas pendientes.'),
                    'type': 'info',
                }
            }
        
        # Agregar mensaje en el Lead
        lead.message_post(
            body=_('✅ Se crearon automáticamente %s alerta(s) de cotización de compra desde el wizard.') % len(alerts_created),
        )
        
        # Retornar acción para mostrar las alertas creadas
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alertas Por Cotización Creadas'),
            'res_model': 'purchase.alert',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [a.id for a in alerts_created])],
            'context': {'default_lead_id': lead.id},
        }


class CrmLeadPurchaseAlertWizardLine(models.TransientModel):
    """Línea del wizard para crear alertas de compra."""
    _name = 'crm.lead.purchase.alert.wizard.line'
    _description = 'Línea Wizard Alertas de Compra desde CRM Lead'

    wizard_id = fields.Many2one(
        'crm.lead.purchase.alert.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain="[('type', 'in', ('product', 'consu'))]",
    )
    quantity = fields.Float(
        string='Cantidad Solicitada',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        related='product_id.uom_id',
        readonly=True,
    )
    stock_available = fields.Float(
        string='Stock Disponible',
        compute='_compute_stock_info',
        readonly=True,
        store=False,
    )
    force_create = fields.Boolean(
        string='Crear Alerta de Todas Formas',
        default=False,
        help='Marcar si desea crear la alerta incluso si hay stock disponible',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Actualizar unidad de medida cuando cambia el producto."""
        for line in self:
            if line.product_id:
                line.uom_id = line.product_id.uom_id

    @api.depends('product_id', 'wizard_id.lead_id')
    def _compute_stock_info(self):
        """Calcular stock disponible para el producto."""
        for line in self:
            if not line.product_id:
                line.stock_available = 0.0
                continue
            
            # Obtener almacén por defecto
            warehouse = self.env['stock.warehouse'].search([], limit=1)
            if not warehouse:
                line.stock_available = 0.0
                continue
            
            location = warehouse.lot_stock_id
            try:
                # Usar sudo() para _gather y luego filtrar solo los accesibles
                all_quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                # Filtrar solo los quants que el usuario actual puede leer
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        continue
                line.stock_available = sum(accessible_quants.mapped('quantity'))
            except Exception:
                line.stock_available = 0.0

