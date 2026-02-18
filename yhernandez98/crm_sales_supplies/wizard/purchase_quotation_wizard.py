# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class PurchaseQuotationWizard(models.TransientModel):
    """Wizard para crear cotizaciones de compra a múltiples proveedores."""
    _name = 'purchase.quotation.wizard'
    _description = 'Wizard para Cotización de Compra a Múltiples Proveedores'

    alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta de Compra',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='alert_id.product_id',
        readonly=True,
    )
    quantity_missing = fields.Float(
        string='Cantidad Faltante',
        related='alert_id.quantity_missing',
        readonly=True,
    )
    vendor_ids = fields.Many2many(
        'res.partner',
        'purchase_quotation_wizard_vendor_rel',
        'wizard_id',
        'vendor_id',
        string='Proveedores',
        domain="['|', ('tipo_contacto', 'in', ['proveedor', 'ambos']), ('supplier_rank', '>', 0)]",
        required=True,
        help='Seleccione los proveedores a los que desea enviar la cotización.',
    )
    notes = fields.Text(
        string='Notas Adicionales',
        help='Notas que se agregarán a todas las órdenes de compra',
    )

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto."""
        res = super().default_get(fields_list)
        
        if 'alert_id' in fields_list and self.env.context.get('active_id'):
            alert_id = self.env.context.get('active_id')
            alert = self.env['purchase.alert'].browse(alert_id)
            if alert.exists():
                res['alert_id'] = alert.id
                # NO cargar proveedores por defecto - el usuario debe seleccionarlos manualmente
        
        return res

    def action_create_quotations(self):
        """Crear órdenes de compra para cada proveedor seleccionado."""
        self.ensure_one()
        
        if not self.vendor_ids:
            raise UserError(_('Debe seleccionar al menos un proveedor.'))
        
        if not self.alert_id:
            raise UserError(_('No se encontró la alerta de compra.'))
        
        alert = self.alert_id
        
        if alert.state != 'pending':
            raise UserError(_('Solo se pueden crear cotizaciones desde alertas pendientes.'))
        
        if not alert.alert_line_ids:
            raise UserError(_('Esta alerta no tiene productos definidos. No se puede crear una orden de compra.'))
        
        purchase_orders_created = []
        warehouse = alert.warehouse_id
        
        if not warehouse:
            raise UserError(_('La alerta no tiene almacén configurado.'))
        
        # Verificar que el almacén tenga picking_type_id configurado
        if not warehouse.in_type_id:
            raise UserError(_('El almacén %s no tiene configurado el tipo de operación de entrada.') % warehouse.name)
        
        # Preparar descripción base
        origin_text = alert.name
        if alert.sale_order_id:
            origin_text = _('Alerta: %s - %s') % (alert.name, alert.sale_order_id.name)
        
        description_base = _('Para cliente: %s') % (alert.partner_id.display_name if alert.partner_id else 'N/A')
        if alert.sale_order_id:
            description_base += ' - %s' % alert.sale_order_id.name
        if self.notes:
            description_base += '\n' + self.notes
        
        # Crear una orden de compra para cada proveedor
        for vendor in self.vendor_ids:
            try:
                # Validar que el proveedor sea válido
                if vendor.supplier_rank == 0:
                    _logger.warning("Proveedor %s no tiene supplier_rank > 0, pero se intentará crear la orden", vendor.display_name)
                
                # Preparar valores base para la orden de compra
                purchase_vals = {
                    'partner_id': vendor.id,
                    'origin': origin_text,
                    'picking_type_id': warehouse.in_type_id.id,
                    'date_order': fields.Datetime.now(),
                    'order_line': [],
                }
                
                # Agregar una línea por cada producto en la alerta
                for alert_line in alert.alert_line_ids:
                    product = alert_line.product_id
                    quantity = int(alert_line.quantity_missing) or int(alert_line.quantity_requested)
                    uom = alert_line.uom_id or product.uom_id
                    
                    # Buscar información del proveedor para este producto
                    seller = None
                    try:
                        seller = product._select_seller(
                            partner_id=vendor.id,
                            quantity=quantity,
                            date=fields.Date.today(),
                            uom_id=uom.id if uom else None,
                        )
                    except Exception as e:
                        _logger.warning("No se pudo obtener seller para proveedor %s y producto %s: %s", vendor.display_name, product.name, str(e))
                    
                    # Determinar el precio unitario
                    if seller and seller.price and seller.price > 0:
                        price_unit = seller.price
                    else:
                        price_unit = product.standard_price or 0.0
                        if price_unit == 0:
                            _logger.warning("Producto %s tiene precio estándar 0, se creará la orden con precio 0", product.name)
                    
                    # Preparar descripción para esta línea
                    description = description_base
                    if len(alert.alert_line_ids) > 1:
                        description += '\n' + _('Producto: %s') % product.display_name
                    
                    # Agregar línea de orden
                    order_line_vals = {
                        'product_id': product.id,
                        'product_qty': quantity,
                        'product_uom': uom.id if uom else product.uom_id.id,
                        'price_unit': price_unit,
                        'date_planned': fields.Datetime.now(),
                        'name': description,
                    }
                    
                    # Si hay seller, agregar información adicional
                    if seller and seller.delay:
                        order_line_vals['date_planned'] = fields.Datetime.now() + timedelta(days=seller.delay)
                    
                    purchase_vals['order_line'].append((0, 0, order_line_vals))
                
                # Crear la orden de compra solo si hay líneas
                if purchase_vals['order_line']:
                    # Agregar sale_order_ids solo si existe y el campo existe en el modelo
                    if alert.sale_order_id:
                        PurchaseOrder = self.env['purchase.order']
                        if 'sale_order_ids' in PurchaseOrder._fields:
                            purchase_vals['sale_order_ids'] = [(4, alert.sale_order_id.id)]
                        elif 'sale_id' in PurchaseOrder._fields:
                            purchase_vals['sale_id'] = alert.sale_order_id.id
                    
                    # Crear orden de compra
                    purchase_order = self.env['purchase.order'].create(purchase_vals)
                    
                    # Agregar la orden a la alerta
                    alert.write({
                        'purchase_order_ids': [(4, purchase_order.id)],
                    })
                    
                    purchase_orders_created.append(purchase_order)
                    
                    _logger.info("Orden de compra %s creada para proveedor %s desde alerta %s con %s líneas", 
                               purchase_order.name, vendor.display_name, alert.name, len(purchase_vals['order_line']))
                
            except Exception as e:
                error_msg = str(e)
                _logger.error("Error creando orden de compra para proveedor %s: %s", 
                            vendor.display_name, error_msg, exc_info=True)
                # Mostrar un mensaje más descriptivo al usuario
                raise UserError(_('Error al crear orden de compra para proveedor %s:\n%s\n\nPor favor, verifique la configuración del proveedor y del producto.') % (vendor.display_name, error_msg))
        
        if not purchase_orders_created:
            raise UserError(_('No se pudo crear ninguna orden de compra. Verifique los proveedores seleccionados.'))
        
        # Actualizar estado de la alerta
        alert.write({
            'state': 'purchase_created',
        })
        
        # Si solo se creó una, también vincularla como principal
        if len(purchase_orders_created) == 1:
            alert.write({
                'purchase_order_id': purchase_orders_created[0].id,
            })
        
        # Agregar mensaje en la alerta
        alert.message_post(
            body=_('✅ Se crearon %s orden(es) de compra para %s proveedor(es):\n%s') % (
                len(purchase_orders_created),
                len(self.vendor_ids),
                '\n'.join(['- %s: %s' % (po.partner_id.display_name, po.name) for po in purchase_orders_created])
            ),
        )
        
        # Retornar acción para mostrar las órdenes creadas
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cotizaciones Solicitadas'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [po.id for po in purchase_orders_created])],
            'context': {'create': False},
        }

