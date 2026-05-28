# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseAlertValidationWizard(models.TransientModel):
    """Wizard para validar cotizaciones por el jefe de CRM."""
    _name = 'purchase.alert.validation.wizard'
    _description = 'Wizard para Validar Cotizaciones de Alerta'

    alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta de Compra',
        required=True,
        readonly=True,
    )
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Cotizaciones a Validar',
        help='Cotizaciones que serán validadas. Puede hacer clic en cada una para ver el detalle completo. Marque la casilla "Aprobada" para aprobar cada cotización.',
    )
    validation_notes = fields.Text(
        string='Notas de Validación',
        help='Comentarios generales sobre la validación de las cotizaciones',
        placeholder='Ej: Se aprobó la cotización del proveedor X por mejor precio...',
    )

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto."""
        res = super().default_get(fields_list)
        
        if 'alert_id' in fields_list and self.env.context.get('default_alert_id'):
            alert_id = self.env.context.get('default_alert_id')
            alert = self.env['purchase.alert'].browse(alert_id)
            if alert.exists():
                res['alert_id'] = alert.id
                if 'purchase_order_ids' in fields_list:
                    res['purchase_order_ids'] = [(6, 0, alert.purchase_order_ids.ids)]
        
        return res

    def action_view_purchase_order_detail(self):
        """Ver el detalle completo de una cotización específica."""
        self.ensure_one()
        
        # Obtener el ID de la cotización desde el contexto
        active_id = self.env.context.get('active_id')
        if not active_id:
            # Intentar obtener desde active_ids
            active_ids = self.env.context.get('active_ids', [])
            if active_ids:
                active_id = active_ids[0]
        
        if not active_id:
            raise UserError(_('No se pudo identificar la cotización a ver.'))
        
        po = self.env['purchase.order'].browse(active_id)
        if not po.exists():
            raise UserError(_('La cotización no existe.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cotización: %s') % po.name,
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'create': False},
        }
    
    def action_validate(self):
        """Validar la alerta (marcar como revisada)."""
        self.ensure_one()
        
        if not self.alert_id:
            raise UserError(_('No se encontró la alerta de compra.'))
        
        # Actualizar las cotizaciones con la información de aprobación/rechazo
        approved_orders = []
        rejected_orders = []
        
        for po in self.purchase_order_ids:
            if po.approved_by_crm:
                # Si está marcada como aprobada, actualizar información
                if not po.approved_by_crm_user_id:
                    po.write({
                        'approved_by_crm_user_id': self.env.user.id,
                        'approved_by_crm_date': fields.Datetime.now(),
                    })
                approved_orders.append(po)
            else:
                # Si no está aprobada, marcarla como rechazada automáticamente
                po.write({
                    'rejected_by_crm': True,
                    'rejected_by_crm_user_id': self.env.user.id,
                    'rejected_by_crm_date': fields.Datetime.now(),
                    'approved_by_crm': False,
                    'approved_by_crm_user_id': False,
                    'approved_by_crm_date': False,
                    'approval_notes': False,
                })
                rejected_orders.append(po)
        
        # Permitir validar sin aprobar ninguna cotización
        # Si no hay ninguna aprobada, todas serán rechazadas automáticamente
        # (Ya se marcaron como rechazadas en el loop anterior)
        
        # Validar la alerta
        self.alert_id.write({
            'validated_by_crm': True,
            'validated_by_user_id': self.env.user.id,
            'validated_date': fields.Datetime.now(),
            'validation_notes': self.validation_notes,
        })

        # Si se aprobaron cotizaciones, llevar automáticamente sus productos
        # a la cotización del cliente relacionada con la alerta.
        self._sync_sale_order_lines_from_approved_quotes(approved_orders)
        
        # Crear mensaje con detalles de las cotizaciones aprobadas y rechazadas
        approved_list = '\n'.join(['- %s: %s' % (po.name, po.partner_id.display_name) for po in approved_orders])
        rejected_list = '\n'.join(['- %s: %s' % (po.name, po.partner_id.display_name) for po in rejected_orders])
        
        message_body = _('''
        <div class="o_mail_notification">
            <p><strong>✅ Alerta Validada por CRM - %s</strong></p>
            <p><strong>Fecha de Validación:</strong> %s</p>
            <p><strong>✅ Cotizaciones Aprobadas (%s):</strong></p>
            <ul>%s</ul>
            <p><strong>❌ Cotizaciones Rechazadas (%s):</strong></p>
            <ul>%s</ul>
            %s
        </div>
        ''') % (
            self.env.user.name,
            fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            len(approved_orders),
            approved_list if approved_list else '<li>Ninguna</li>',
            len(rejected_orders),
            rejected_list if rejected_list else '<li>Ninguna</li>',
            '<p><strong>Notas:</strong> %s</p>' % self.validation_notes if self.validation_notes else ''
        )
        
        # Enviar mensaje
        self.alert_id.message_post(
            body=message_body,
            subject=_('✅ Validación: %s') % self.alert_id.name,
            message_type='notification',
        )
        
        # Mensaje según si hay aprobadas o no
        if approved_orders:
            message = _('La alerta ha sido validada. %s cotización(es) aprobada(s), %s rechazada(s).') % (len(approved_orders), len(rejected_orders))
            msg_type = 'success'
        else:
            message = _('La alerta ha sido validada. Todas las cotizaciones fueron rechazadas (%s rechazada(s)).') % len(rejected_orders)
            msg_type = 'warning'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Alerta validada'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }

    def _sync_sale_order_lines_from_approved_quotes(self, approved_orders):
        """Crear/actualizar líneas en la cotización cliente desde compras aprobadas."""
        self.ensure_one()
        sale_order = self.alert_id.sale_order_id
        if not sale_order or not approved_orders:
            return
        if sale_order.state not in ('draft', 'sent'):
            return

        SaleOrderLine = self.env['sale.order.line'].with_context(skip_auto_create_alerts=True)
        for po in approved_orders:
            for po_line in po.order_line.filtered(lambda l: l.product_id):
                product = po_line.product_id
                # Usar la UoM de venta del producto y convertir cantidad de compra.
                sale_uom = product.uom_id
                purchase_uom = po_line.product_uom_id or product.uom_po_id or sale_uom
                qty = purchase_uom._compute_quantity(po_line.product_qty, sale_uom)

                existing_line = sale_order.order_line.filtered(
                    lambda l: l.purchase_origin_line_id.id == po_line.id
                )[:1]

                if existing_line:
                    existing_line.write({
                        'product_uom_qty': qty,
                    })
                    continue

                try:
                    price_unit = sale_order.pricelist_id._get_product_price(
                        product, qty or 1.0, sale_order.partner_id
                    ) if sale_order.pricelist_id else (product.lst_price or 0.0)
                except Exception:
                    price_unit = product.lst_price or 0.0

                line_name = (
                    product.get_product_multiline_description_sale()
                    if hasattr(product, 'get_product_multiline_description_sale')
                    else product.display_name
                )
                SaleOrderLine.create({
                    'order_id': sale_order.id,
                    'product_id': product.id,
                    'name': line_name or product.display_name,
                    'product_uom_qty': qty or 1.0,
                    'product_uom_id': sale_uom.id,
                    'price_unit': price_unit or 0.0,
                    'purchase_origin_line_id': po_line.id,
                })

