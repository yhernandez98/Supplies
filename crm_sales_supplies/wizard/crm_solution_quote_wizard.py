# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmSolutionQuoteWizard(models.TransientModel):
    _name = 'crm.solution.quote.wizard'
    _description = 'Wizard para Armar Solucion CRM'

    lead_id = fields.Many2one('crm.lead', required=False, string='Oportunidad')
    sale_order_id = fields.Many2one('sale.order', string='Cotizacion')
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        compute='_compute_partner_id',
        readonly=True,
        store=False,
    )
    location_id = fields.Many2one('stock.location', string='Ubicacion Cliente')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacen', required=True)
    available_subscription_ids = fields.Many2many(
        'subscription.subscription',
        compute='_compute_available_subscription_ids',
        string='Suscripciones disponibles',
    )
    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripcion destino',
        domain="[('id', 'in', available_subscription_ids)]",
    )
    final_service_name = fields.Char(string='Nombre del paquete/servicio')
    package_total_price = fields.Float(string='Precio final del paquete')
    line_ids = fields.One2many('crm.solution.quote.wizard.line', 'wizard_id', string='Lineas')

    @api.depends('lead_id', 'sale_order_id')
    def _compute_partner_id(self):
        for rec in self:
            rec.partner_id = (
                rec.sale_order_id.partner_id
                or rec.lead_id.partner_id
                or False
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead_id = self.env.context.get('active_id') if self.env.context.get('active_model') == 'crm.lead' else False
        sale_order_id = self.env.context.get('active_id') if self.env.context.get('active_model') == 'sale.order' else False
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead.exists():
                res['lead_id'] = lead.id
                res['location_id'] = lead.location_id.id if getattr(lead, 'location_id', False) else False
        elif sale_order_id:
            so = self.env['sale.order'].browse(sale_order_id)
            if so.exists():
                res['sale_order_id'] = so.id
                res['lead_id'] = so.opportunity_id.id if so.opportunity_id else False
                if so.partner_id and so.partner_id.property_stock_customer:
                    res['location_id'] = so.partner_id.property_stock_customer.id
        if not res.get('warehouse_id'):
            wh = self.env['stock.warehouse'].search([], limit=1)
            if wh:
                res['warehouse_id'] = wh.id
        if not res.get('location_id') and res.get('lead_id'):
            lead = self.env['crm.lead'].browse(res['lead_id'])
            if lead.partner_id and lead.partner_id.property_stock_customer:
                res['location_id'] = lead.partner_id.property_stock_customer.id
        return res

    @api.depends('partner_id')
    def _compute_available_subscription_ids(self):
        Sub = self.env['subscription.subscription']
        for rec in self:
            if rec.partner_id:
                rec.available_subscription_ids = Sub.search([('partner_id', '=', rec.partner_id.id)])
            else:
                rec.available_subscription_ids = Sub.browse([])

    def action_create_quote(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Debe agregar al menos una linea.'))
        quote = self.env['crm.solution.quote'].create({
            'lead_id': self.lead_id.id if self.lead_id else False,
            'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
            'location_id': self.location_id.id if self.location_id else False,
            'warehouse_id': self.warehouse_id.id,
            'subscription_target_id': self.subscription_id.id if self.subscription_id else False,
            'final_service_name': self.final_service_name or '',
            'package_total_price': self.package_total_price or 0.0,
        })
        for line in self.line_ids:
            self.env['crm.solution.quote.line'].create({
                'quote_id': quote.id,
                'line_type': line.line_type,
                'product_id': line.product_id.id if line.product_id else False,
                'description': line.description or (line.product_id.display_name if line.product_id else ''),
                'quantity': line.quantity,
                'cost_unit': line.cost_unit,
                'price_unit': line.price_unit,
                'requires_purchase_alert': line.requires_purchase_alert,
                'to_subscription': line.to_subscription,
                'to_delivery': line.to_delivery,
            })
        # Reflejar inmediatamente el combo en las líneas de la cotización de venta.
        if self.sale_order_id:
            self._append_solution_lines_to_sale_order(self.sale_order_id, quote)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.solution.quote',
            'view_mode': 'form',
            'res_id': quote.id,
            'target': 'current',
        }

    def _append_solution_lines_to_sale_order(self, sale_order, quote):
        """Agrega a la cotización una única línea de paquete con precio y una nota de contenido."""
        self.ensure_one()
        if not sale_order or not quote:
            return

        SaleOrderLine = self.env['sale.order.line']
        package_product = self._get_or_create_package_product()

        package_name = (self.final_service_name or '').strip() or _('Paquete comercial')
        package_price = self.package_total_price or sum(self.line_ids.mapped('price_unit')) or 0.0

        SaleOrderLine.create({
            'order_id': sale_order.id,
            'product_id': package_product.id,
            'name': package_name,
            'product_uom_qty': 1.0,
            'price_unit': package_price,
            'sequence': 9990,
        })

        content_lines = []
        for line in self.line_ids.filtered(lambda l: l.product_id and (l.quantity or 0.0) > 0):
            content_lines.append('- %s x %s' % (line.product_id.display_name, line.quantity))
        if content_lines:
            SaleOrderLine.create({
                'order_id': sale_order.id,
                'display_type': 'line_note',
                'name': _('Contenido del paquete:\n%s') % '\n'.join(content_lines),
                'sequence': 9991,
            })

    def _get_or_create_package_product(self):
        """Producto de servicio técnico para representar paquetes comerciales en cotización."""
        Product = self.env['product.product']
        product = Product.search([('default_code', '=', 'CRM_PACKAGE_LINE')], limit=1)
        if product:
            return product
        tmpl = self.env['product.template'].create({
            'name': _('Paquete comercial CRM'),
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': False,
            'list_price': 0.0,
        })
        product = tmpl.product_variant_id
        product.default_code = 'CRM_PACKAGE_LINE'
        return product


class CrmSolutionQuoteWizardLine(models.TransientModel):
    _name = 'crm.solution.quote.wizard.line'
    _description = 'Linea Wizard Solucion CRM'

    wizard_id = fields.Many2one('crm.solution.quote.wizard', required=True, ondelete='cascade')
    line_type = fields.Selection(
        [('equipment', 'Equipo'), ('license', 'Licencia'), ('service', 'Servicio')],
        default='equipment',
        required=True,
        string='Tipo',
    )
    product_id = fields.Many2one('product.product', string='Producto')
    allowed_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_allowed_product_ids',
        string='Productos permitidos',
    )
    description = fields.Char(string='Descripcion')
    quantity = fields.Float(default=1.0, string='Cantidad')
    cost_unit = fields.Float(string='Costo Unitario')
    price_unit = fields.Float(string='Precio Unitario')
    available_qty = fields.Float(string='Disponible', compute='_compute_availability', readonly=True)
    missing_qty = fields.Float(string='Faltante', compute='_compute_availability', readonly=True)
    availability_status = fields.Selection(
        [('available', 'Disponible'), ('partial', 'Parcial'), ('missing', 'Sin stock')],
        compute='_compute_availability',
        readonly=True,
    )
    requires_purchase_alert = fields.Boolean(default=True)
    to_subscription = fields.Boolean(default=True)
    to_delivery = fields.Boolean(default=True)

    @api.depends('line_type')
    def _compute_allowed_product_ids(self):
        Product = self.env['product.product']
        license_product_ids = set()

        # 1) Licencias desde plantillas (módulo subscription_licenses)
        if 'license.template' in self.env:
            try:
                license_product_ids |= set(
                    self.env['license.template'].sudo().search([]).mapped('product_id').ids
                )
            except Exception:
                pass

        # 2) Licencias desde asignaciones activas/históricas (fuente principal en varios entornos)
        if 'license.assignment' in self.env:
            try:
                license_product_ids |= set(
                    self.env['license.assignment'].sudo().search([]).mapped('license_id.product_id').ids
                )
            except Exception:
                pass

        license_product_ids = {pid for pid in license_product_ids if pid}
        for rec in self:
            if rec.line_type == 'service':
                rec.allowed_product_ids = Product.search([('type', '=', 'service')])
            elif rec.line_type == 'license':
                if license_product_ids:
                    rec.allowed_product_ids = Product.browse(list(license_product_ids))
                else:
                    # Fallback: mostrar servicios con nombre/código de licencia para no dejar el selector vacío.
                    rec.allowed_product_ids = Product.search([
                        ('type', '=', 'service'),
                        '|', '|',
                        ('name', 'ilike', 'licenc'),
                        ('default_code', 'ilike', 'LIC'),
                        ('display_name', 'ilike', 'licenc'),
                    ])
            else:
                domain = [('type', 'in', ('product', 'consu'))]
                equipment_products = Product.search(domain)
                if license_product_ids:
                    equipment_products = equipment_products.filtered(lambda p: p.id not in license_product_ids)
                rec.allowed_product_ids = equipment_products

    @api.onchange('line_type')
    def _onchange_line_type(self):
        for rec in self:
            rec.product_id = False
            rec.description = False
        return {'domain': {'product_id': [('id', 'in', self.allowed_product_ids.ids)]}}

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.description = rec.product_id.display_name
                rec.cost_unit = rec.product_id.standard_price or 0.0
                if rec.price_unit <= 0:
                    rec.price_unit = rec.product_id.lst_price or 0.0

    @api.depends('product_id', 'quantity', 'wizard_id.warehouse_id', 'line_type')
    def _compute_availability(self):
        for rec in self:
            if not rec.product_id or rec.line_type == 'service':
                rec.available_qty = rec.quantity or 0.0
                rec.missing_qty = 0.0
                rec.availability_status = 'available'
                rec.requires_purchase_alert = False
                continue
            warehouse = rec.wizard_id.warehouse_id
            if not warehouse:
                rec.available_qty = 0.0
                rec.missing_qty = rec.quantity or 0.0
                rec.availability_status = 'missing'
                rec.requires_purchase_alert = rec.missing_qty > 0
                continue
            location = warehouse.lot_stock_id
            try:
                quants = self.env['stock.quant'].sudo()._gather(rec.product_id, location)
                available = sum(quants.mapped('quantity'))
            except Exception:
                available = rec.product_id.qty_available or 0.0
            rec.available_qty = max(0.0, available)
            rec.missing_qty = max(0.0, (rec.quantity or 0.0) - rec.available_qty)
            rec.requires_purchase_alert = rec.missing_qty > 0
            if rec.missing_qty <= 0:
                rec.availability_status = 'available'
            elif rec.available_qty > 0:
                rec.availability_status = 'partial'
            else:
                rec.availability_status = 'missing'
