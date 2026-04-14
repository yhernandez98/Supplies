# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmSolutionPricingRule(models.Model):
    _name = 'crm.solution.pricing.rule'
    _description = 'Regla de Pricing para Solucion CRM'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    applies_to = fields.Selection(
        [
            ('equipment', 'Equipo'),
            ('license', 'Licencia'),
            ('service', 'Servicio'),
            ('all', 'Todos'),
        ],
        default='all',
        required=True,
    )
    method = fields.Selection(
        [
            ('fixed', 'Precio Fijo'),
            ('cost_plus_pct', 'Costo + Margen (%)'),
            ('manual_with_floor', 'Manual con Margen Minimo'),
        ],
        default='cost_plus_pct',
        required=True,
    )
    fixed_price = fields.Float(string='Precio Fijo')
    markup_percent = fields.Float(string='Margen %', default=20.0)
    min_margin_percent = fields.Float(string='Margen Minimo %', default=10.0)


class CrmSolutionLicenseParam(models.Model):
    _name = 'crm.solution.license.param'
    _description = 'Parametro de Licencias para Solucion CRM'
    _order = 'product_categ_id'

    active = fields.Boolean(default=True)
    product_categ_id = fields.Many2one('product.category', string='Categoria de Producto', required=True)
    default_rule_id = fields.Many2one('crm.solution.pricing.rule', string='Regla por Defecto')
    currency_mode = fields.Selection(
        [('cop', 'COP'), ('usd_trm', 'USD con TRM')],
        default='usd_trm',
        required=True,
    )
    min_margin_percent = fields.Float(string='Margen Minimo %', default=10.0)


class CrmSolutionQuote(models.Model):
    _name = 'crm.solution.quote'
    _description = 'Propuesta de Solucion Comercial CRM'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(default=lambda self: _('Nueva Propuesta'), readonly=True, copy=False)
    lead_id = fields.Many2one('crm.lead', string='Oportunidad', required=False, ondelete='set null', tracking=True)
    sale_order_id = fields.Many2one('sale.order', string='Cotizacion', ondelete='cascade', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', related='lead_id.partner_id', store=True, readonly=True)
    location_id = fields.Many2one('stock.location', string='Ubicacion Cliente')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacen', required=True)
    subscription_target_id = fields.Many2one('subscription.subscription', string='Suscripcion destino')
    final_service_name = fields.Char(string='Nombre del servicio final')
    package_total_price = fields.Float(string='Precio final del paquete')
    subscription_id = fields.Many2one('subscription.subscription', string='Suscripcion Generada', readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Borrador'), ('review', 'En Revision'), ('approved', 'Aprobada'), ('cancelled', 'Cancelada')],
        default='draft',
        tracking=True,
        required=True,
    )
    version = fields.Integer(default=1)
    is_current = fields.Boolean(default=True)
    line_ids = fields.One2many('crm.solution.quote.line', 'quote_id', string='Lineas')
    purchase_alert_ids = fields.Many2many('purchase.alert', string='Alertas Generadas', readonly=True, copy=False)
    picking_ids = fields.Many2many('stock.picking', string='Entregas Generadas', readonly=True, copy=False)
    total_cost = fields.Float(compute='_compute_totals', string='Costo Total', store=True)
    total_price = fields.Float(compute='_compute_totals', string='Precio Total', store=True)
    margin_amount = fields.Float(compute='_compute_totals', string='Margen', store=True)
    margin_percent = fields.Float(compute='_compute_totals', string='Margen %', store=True)
    approved_date = fields.Datetime(readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('Nueva Propuesta'):
                vals['name'] = self.env['ir.sequence'].next_by_code('crm.solution.quote') or _('Nueva Propuesta')
            if not vals.get('warehouse_id'):
                warehouse = self.env['stock.warehouse'].search([], limit=1)
                vals['warehouse_id'] = warehouse.id if warehouse else False
        return super().create(vals_list)

    @api.depends('line_ids.cost_total', 'line_ids.price_total')
    def _compute_totals(self):
        for rec in self:
            rec.total_cost = sum(rec.line_ids.mapped('cost_total'))
            line_total_price = sum(rec.line_ids.mapped('price_total'))
            rec.total_price = rec.package_total_price or line_total_price
            rec.margin_amount = rec.total_price - rec.total_cost
            rec.margin_percent = (rec.margin_amount / rec.total_cost * 100.0) if rec.total_cost else 0.0

    def action_mark_review(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'review'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_validate_availability(self):
        self.ensure_one()
        for line in self.line_ids:
            line._compute_available_qty()
        self.action_mark_review()
        return True

    def action_approve(self):
        self.ensure_one()
        if self.state not in ('draft', 'review'):
            raise UserError(_('Solo puede aprobar propuestas en borrador o en revision.'))
        if not self.line_ids:
            raise UserError(_('Debe agregar al menos una linea en la propuesta.'))

        self.action_validate_availability()
        self._create_purchase_alerts_for_missing_lines()
        self._apply_to_subscription()
        self._create_delivery_for_available_lines()
        self.write({
            'state': 'approved',
            'approved_date': fields.Datetime.now(),
            'approved_by': self.env.user.id,
        })
        if self.lead_id:
            self.lead_id.message_post(body=_('Se aprobo la propuesta %s.') % self.display_name)
        return True

    def _apply_to_subscription(self):
        self.ensure_one()
        if not self.partner_id:
            return
        sub_lines = self.line_ids.filtered(lambda l: l.to_subscription and l.product_id and l.quantity > 0)
        if not sub_lines:
            return
        products = []
        for line in sub_lines:
            products.append({
                'product': line.product_id,
                'quantity': line.quantity,
                'price': line.price_unit,
            })
        location = self.location_id or self.lead_id.location_id or self.partner_id.property_stock_customer
        if self.subscription_target_id:
            subscription = self.subscription_target_id
            subscription._sync_subscription_lines(products, remove_missing=False, track_usage=True)
        else:
            subscription = self.env['subscription.subscription'].ensure_subscription(
                partner=self.partner_id,
                location=location,
                products=products,
                remove_missing=False,
                track_usage=True,
            )
        self.subscription_id = subscription.id

    def _create_delivery_for_available_lines(self):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda l: l.to_delivery and l.product_id and l.product_id.type in ('product', 'consu') and l.available_qty > 0
        )
        if not lines or not self.warehouse_id:
            return
        picking_type = self.warehouse_id.out_type_id
        if not picking_type:
            return
        customer_location = self.partner_id.property_stock_customer
        if not customer_location:
            customer_location = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        if not customer_location:
            return
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id or self.warehouse_id.lot_stock_id.id,
            'location_dest_id': customer_location.id,
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'note': _('Generado desde propuesta CRM %s') % self.display_name,
        }
        picking = self.env['stock.picking'].create(picking_vals)
        for line in lines:
            qty = min(line.quantity, line.available_qty)
            if qty <= 0:
                continue
            self.env['stock.move'].create({
                'name': line.description or line.product_id.display_name,
                'picking_id': picking.id,
                'picking_type_id': picking.picking_type_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': qty,
            })
        if picking.move_ids_without_package:
            picking.action_confirm()
            picking.action_assign()
            self.picking_ids = [(4, picking.id)]

    def _create_purchase_alerts_for_missing_lines(self):
        self.ensure_one()
        if not self.warehouse_id:
            return
        created = self.env['purchase.alert']
        lead = self.lead_id or self.sale_order_id.opportunity_id
        for line in self.line_ids.filtered(lambda l: l.requires_purchase_alert and l.missing_qty > 0 and l.product_id):
            alert = self.env['purchase.alert'].create({
                'lead_id': lead.id if lead else False,
                'partner_id': self.partner_id.id if self.partner_id else False,
                'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
                'warehouse_id': self.warehouse_id.id,
                'notes': _('Faltante desde propuesta %s') % self.display_name,
                'alert_line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'quantity_requested': line.missing_qty,
                })],
            })
            line.purchase_alert_id = alert.id
            created |= alert
        if created:
            self.purchase_alert_ids = [(6, 0, created.ids)]

    def action_new_revision(self):
        self.ensure_one()
        new_vals = {
            'lead_id': self.lead_id.id,
            'sale_order_id': self.sale_order_id.id,
            'location_id': self.location_id.id,
            'warehouse_id': self.warehouse_id.id,
            'version': self.version + 1,
            'state': 'draft',
        }
        new_quote = self.create(new_vals)
        for line in self.line_ids:
            line.copy({'quote_id': new_quote.id, 'purchase_alert_id': False})
        self.is_current = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.solution.quote',
            'view_mode': 'form',
            'res_id': new_quote.id,
            'target': 'current',
        }


class CrmSolutionQuoteLine(models.Model):
    _name = 'crm.solution.quote.line'
    _description = 'Linea de Propuesta CRM'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    quote_id = fields.Many2one('crm.solution.quote', required=True, ondelete='cascade')
    line_type = fields.Selection(
        [('equipment', 'Equipo'), ('license', 'Licencia'), ('service', 'Servicio')],
        default='equipment',
        required=True,
    )
    product_id = fields.Many2one('product.product', string='Producto/Servicio')
    description = fields.Char()
    quantity = fields.Float(default=1.0)
    pricing_rule_id = fields.Many2one('crm.solution.pricing.rule', string='Regla de Precio')
    cost_unit = fields.Float(string='Costo Unitario', digits=(16, 2))
    price_unit = fields.Float(string='Precio Unitario', digits=(16, 2))
    cost_total = fields.Float(compute='_compute_amounts', string='Costo Total', store=True)
    price_total = fields.Float(compute='_compute_amounts', string='Precio Total', store=True)
    available_qty = fields.Float(compute='_compute_available_qty', string='Disponible', store=False)
    missing_qty = fields.Float(compute='_compute_available_qty', string='Faltante', store=False)
    fulfillment_state = fields.Selection(
        [('available', 'Disponible'), ('partial', 'Parcial'), ('missing', 'Sin stock')],
        compute='_compute_available_qty',
        store=False,
    )
    requires_purchase_alert = fields.Boolean(default=True, string='Generar alerta por faltante')
    to_subscription = fields.Boolean(default=True, string='Incluir en suscripcion')
    to_delivery = fields.Boolean(default=True, string='Incluir en entrega')
    purchase_alert_id = fields.Many2one('purchase.alert', readonly=True, copy=False)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.description = rec.product_id.display_name
                rec.cost_unit = rec.product_id.standard_price or 0.0
                if rec.price_unit <= 0:
                    rec.price_unit = rec.product_id.lst_price or 0.0

    @api.onchange('pricing_rule_id', 'cost_unit')
    def _onchange_pricing_rule_id(self):
        for rec in self:
            if not rec.pricing_rule_id:
                continue
            rule = rec.pricing_rule_id
            if rule.method == 'fixed':
                rec.price_unit = rule.fixed_price or rec.price_unit
            elif rule.method == 'cost_plus_pct':
                rec.price_unit = rec.cost_unit * (1.0 + (rule.markup_percent or 0.0) / 100.0)
            elif rule.method == 'manual_with_floor':
                min_price = rec.cost_unit * (1.0 + (rule.min_margin_percent or 0.0) / 100.0)
                if rec.price_unit < min_price:
                    rec.price_unit = min_price

    @api.depends('quantity', 'cost_unit', 'price_unit')
    def _compute_amounts(self):
        for rec in self:
            rec.cost_total = (rec.quantity or 0.0) * (rec.cost_unit or 0.0)
            rec.price_total = (rec.quantity or 0.0) * (rec.price_unit or 0.0)

    @api.depends('product_id', 'quantity', 'quote_id.warehouse_id')
    def _compute_available_qty(self):
        for rec in self:
            if not rec.product_id or rec.line_type == 'service':
                rec.available_qty = rec.quantity or 0.0
                rec.missing_qty = 0.0
                rec.fulfillment_state = 'available'
                continue
            warehouse = rec.quote_id.warehouse_id
            if not warehouse:
                rec.available_qty = 0.0
                rec.missing_qty = rec.quantity or 0.0
                rec.fulfillment_state = 'missing'
                continue
            location = warehouse.lot_stock_id
            try:
                quants = self.env['stock.quant'].sudo()._gather(rec.product_id, location)
                available = sum(quants.mapped('quantity'))
            except Exception:
                available = rec.product_id.qty_available or 0.0
            rec.available_qty = max(0.0, available)
            rec.missing_qty = max(0.0, (rec.quantity or 0.0) - rec.available_qty)
            if rec.missing_qty <= 0:
                rec.fulfillment_state = 'available'
            elif rec.available_qty > 0:
                rec.fulfillment_state = 'partial'
            else:
                rec.fulfillment_state = 'missing'
