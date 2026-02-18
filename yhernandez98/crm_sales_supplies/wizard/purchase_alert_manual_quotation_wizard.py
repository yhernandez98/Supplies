# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class PurchaseAlertManualQuotationWizard(models.TransientModel):
    """Wizard para crear cotización manual desde alerta sin productos específicos."""
    _name = 'purchase.alert.manual.quotation.wizard'
    _description = 'Wizard para Crear Cotización Manual desde Alerta'

    alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta de Compra',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='alert_id.partner_id',
        readonly=True,
        store=False,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Oportunidad',
        related='alert_id.lead_id',
        readonly=True,
        store=False,
    )
    description = fields.Text(
        string='Descripción de lo que se necesita cotizar',
        required=True,
        help='Describe los productos o servicios que necesita cotizar. Esta información se usará en la orden de compra.',
    )
    vendor_ids = fields.Many2many(
        'res.partner',
        'purchase_alert_manual_quotation_wizard_vendor_rel',
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
                # Prellenar descripción con las notas de la alerta
                if alert.notes:
                    res['description'] = alert.notes
                elif alert.sale_order_id and alert.sale_order_id.note:
                    res['description'] = alert.sale_order_id.note
                elif alert.lead_id and alert.lead_id.description:
                    res['description'] = alert.lead_id.description
        
        return res

    def action_create_quotations(self):
        """Crear órdenes de compra manuales para cada proveedor seleccionado."""
        self.ensure_one()
        
        if not self.vendor_ids:
            raise UserError(_('Debe seleccionar al menos un proveedor.'))
        
        if not self.alert_id:
            raise UserError(_('No se encontró la alerta de compra.'))
        
        if not self.description or not self.description.strip():
            raise UserError(_('Debe especificar una descripción de lo que se necesita cotizar.'))
        
        alert = self.alert_id
        
        if alert.state != 'pending':
            raise UserError(_('Solo se pueden crear cotizaciones desde alertas pendientes.'))
        
        purchase_orders_created = []
        warehouse = alert.warehouse_id
        
        if not warehouse:
            raise UserError(_('La alerta no tiene almacén configurado.'))
        
        # Verificar que el almacén tenga picking_type_id configurado
        if not warehouse.in_type_id:
            raise UserError(_('El almacén %s no tiene configurado el tipo de operación de entrada.') % warehouse.name)
        
        # Preparar descripción base (solo la descripción del usuario, sin información interna)
        origin_text = alert.name
        if alert.sale_order_id:
            origin_text = _('Alerta: %s - %s') % (alert.name, alert.sale_order_id.name)
        
        # Solo usar la descripción proporcionada por el usuario (sin información interna)
        description_base = self.description
        
        if self.notes:
            description_base += '\n\n%s' % self.notes
        
        # Crear una orden de compra para cada proveedor
        for vendor in self.vendor_ids:
            try:
                # Preparar valores base para la orden de compra
                purchase_vals = {
                    'partner_id': vendor.id,
                    'origin': origin_text,
                    'picking_type_id': warehouse.in_type_id.id,
                    'date_order': fields.Datetime.now(),
                    'order_line': [(0, 0, {
                        'product_id': False,  # Sin producto específico
                        'name': description_base,
                        'product_qty': 1.0,
                        'product_uom': False,
                        'price_unit': 0.0,  # Precio a definir
                        'date_planned': fields.Datetime.now(),
                    })],
                }
                
                # Agregar sale_order_ids si existe
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
                
                _logger.info("Orden de compra manual %s creada para proveedor %s desde alerta %s", 
                           purchase_order.name, vendor.display_name, alert.name)
                
            except Exception as e:
                error_msg = str(e)
                _logger.error("Error creando orden de compra para proveedor %s: %s", 
                            vendor.display_name, error_msg, exc_info=True)
                raise UserError(_('Error al crear orden de compra para proveedor %s:\n%s\n\nPor favor, verifique la configuración del proveedor.') % (vendor.display_name, error_msg))
        
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
            body=_('✅ Se crearon %s orden(es) de compra manual(es) para %s proveedor(es):\n%s') % (
                len(purchase_orders_created),
                len(self.vendor_ids),
                '\n'.join(['- %s: %s' % (po.partner_id.display_name, po.name) for po in purchase_orders_created])
            ),
        )
        
        # Retornar acción para mostrar las órdenes creadas
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cotizaciones Creadas'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [po.id for po in purchase_orders_created])],
            'context': {'create': False},
        }

