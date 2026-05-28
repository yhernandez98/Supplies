# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CommercialIntegrationCase(models.Model):
    _name = 'commercial.integration.case'
    _description = 'Caso integración CRM – Compras – Calculadora'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo caso'))
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    lead_id = fields.Many2one('crm.lead', string='Oportunidad', index=True, ondelete='set null')
    sale_order_id = fields.Many2one('sale.order', string='Cotización venta', index=True, ondelete='set null')
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        compute='_compute_partner_id',
        store=True,
        readonly=False,
    )
    purchase_alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta compras',
        index=True,
        ondelete='set null',
    )
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', required=False)

    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('awaiting_quotes', 'Cotizaciones proveedor'),
            ('quote_selected', 'Proveedor ganador'),
            ('calculator_ready', 'Calculadora lista'),
            ('proposal_draft', 'Propuesta borrador'),
            ('proposal_sent', 'Propuesta enviada'),
            ('customer_approved', 'Cliente aprobó'),
            ('customer_rejected', 'Cliente rechazó'),
            ('operations_done', 'Operación ejecutada'),
            ('cancelled', 'Cancelado'),
        ],
        default='draft',
        tracking=True,
        required=True,
    )
    winning_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Cotización ganadora',
        ondelete='set null',
        tracking=True,
        copy=False,
    )
    winning_selected_by = fields.Many2one('res.users', string='Ganador definido por', readonly=True, copy=False)
    winning_selected_date = fields.Datetime(string='Fecha selección ganador', readonly=True, copy=False)

    calculadora_id = fields.Many2one(
        'calculadora.costos',
        string='Calculadora',
        ondelete='set null',
        copy=False,
    )
    proposal_id = fields.Many2one(
        'commercial.customer.proposal',
        string='Propuesta al cliente',
        ondelete='set null',
        copy=False,
    )
    operations_routed = fields.Boolean(
        string='Ruteo operativo ejecutado',
        default=False,
        copy=False,
        help='Evita ejecutar dos veces el flujo bodega/compra automático.',
    )
    last_picking_id = fields.Many2one('stock.picking', string='Última entrega generada', readonly=True, copy=False)
    last_auto_purchase_id = fields.Many2one('purchase.order', string='Última compra auto generada', readonly=True, copy=False)

    @api.depends('lead_id.partner_id', 'sale_order_id.partner_id')
    def _compute_partner_id(self):
        for rec in self:
            rec.partner_id = rec.sale_order_id.partner_id or rec.lead_id.partner_id or False

    _sql_constraints = [
        (
            'commercial_case_winning_po_unique',
            'unique(winning_purchase_order_id)',
            'Ya existe un caso con esta cotización de compra como ganadora.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('Nuevo caso'):
                vals['name'] = self.env['ir.sequence'].next_by_code('commercial.integration.case') or _('Nuevo caso')
        return super().create(vals_list)

    @api.constrains('winning_purchase_order_id')
    def _check_winning_po_approved_by_crm(self):
        for rec in self:
            po = rec.winning_purchase_order_id
            if not po or not po.id:
                continue
            if not getattr(po, 'approved_by_crm', False):
                raise UserError(
                    _('La cotización ganadora debe estar aprobada por CRM antes de vincularla al caso.')
                )

    @api.model
    def get_or_create_for_alert(self, alert):
        """Obtiene o crea un caso por alerta (sin abrir ventana)."""
        if not alert:
            return self.browse()
        found = self.search([('purchase_alert_id', '=', alert.id), ('company_id', '=', self.env.company.id)], limit=1)
        if found:
            return found
        return self.create({
            'lead_id': alert.lead_id.id if alert.lead_id else False,
            'sale_order_id': alert.sale_order_id.id if alert.sale_order_id else False,
            'purchase_alert_id': alert.id,
            'warehouse_id': alert.warehouse_id.id if alert.warehouse_id else False,
            'state': 'awaiting_quotes',
        })

    def action_set_winning_purchase_order(self, purchase_order):
        """Asigna PO ganadora, sincroniza calculadora. Llamado desde purchase.order."""
        self.ensure_one()
        po = purchase_order
        if not po:
            raise UserError(_('Cotización de compra no válida.'))
        if not getattr(po, 'approved_by_crm', False):
            raise UserError(_('Debe aprobar la cotización por CRM antes de marcarla como ganadora.'))
        alert = self.env['purchase.alert'].search([('purchase_order_ids', 'in', po.id)], limit=1)
        if self.purchase_alert_id and alert and alert.id != self.purchase_alert_id.id:
            raise UserError(_('La cotización no pertenece a la alerta de este caso.'))
        if alert and not self.purchase_alert_id:
            self.purchase_alert_id = alert.id
        self.write({
            'winning_purchase_order_id': po.id,
            'winning_selected_by': self.env.user.id,
            'winning_selected_date': fields.Datetime.now(),
            'state': 'quote_selected',
        })
        self._sync_calculadora_from_po(po)
        self.write({'state': 'calculator_ready'})
        self.message_post(
            body=_('Cotización ganadora: %s. Calculadora sincronizada.') % po.display_name,
        )
        return True

    def _sync_calculadora_from_po(self, purchase_order):
        self.ensure_one()
        po = purchase_order
        Calc = self.env['calculadora.costos']
        Line = self.env['calculadora.costos.line']
        cop = self.env.ref('base.COP', raise_if_not_found=False)
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        currency = po.currency_id or self.env.company.currency_id
        moneda_equipo = 'USD' if usd and currency.id == usd.id else 'COP'

        vals = {
            'name': _('%s – Caso %s') % (po.name, self.name),
            'partner_id': self.partner_id.id if self.partner_id else False,
            'calculation_type': 'sale',
            'tipo_operacion': 'venta',
            'integration_case_id': self.id,
            'source_purchase_order_id': po.id,
            'currency_id': currency.id,
            'company_id': self.company_id.id,
            'rate_date': fields.Date.context_today(self),
        }
        if self.calculadora_id:
            calc = self.calculadora_id
            calc.write(vals)
            calc.line_ids.unlink()
        else:
            calc = Calc.create(vals)
            self.calculadora_id = calc.id
            # calculadora.create() agrega una línea por defecto; se reemplaza por líneas de la PO.
            calc.line_ids.unlink()

        seq = 10
        for pol in po.order_line.filtered(lambda l: not l.display_type and l.product_id):
            product = pol.product_id
            if product.type == 'service':
                continue
            qty = pol.product_qty or 0.0
            if qty <= 0:
                continue
            Line.create({
                'calculadora_id': calc.id,
                'sequence': seq,
                'name': pol.name or product.display_name,
                'product_id': product.id,
                'product_qty': qty,
                'price_unit': pol.price_unit or 0.0,
                'moneda_equipo': moneda_equipo,
                'monto_garantia': 0.0,
            })
            seq += 10

        calc.invalidate_recordset()
        return calc

    def action_open_calculadora(self):
        self.ensure_one()
        if not self.calculadora_id:
            raise UserError(_('No hay calculadora. Marque primero la cotización ganadora.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Calculadora'),
            'res_model': 'calculadora.costos',
            'res_id': self.calculadora_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_generate_proposal(self):
        self.ensure_one()
        if not self.calculadora_id:
            if self.purchase_alert_id and self.purchase_alert_id.purchase_order_ids:
                self._sync_calculadora_from_alert_quotes(self.purchase_alert_id)
            else:
                raise UserError(_('No hay calculadora. Sincronice desde cotizaciones o desde la cotización ganadora.'))
        self._sync_sale_order_from_calculadora()
        Proposal = self.env['commercial.customer.proposal']
        if self.proposal_id and self.proposal_id.state not in ('draft', 'cancelled'):
            raise UserError(_('Ya existe una propuesta enviada o cerrada. Cancele la propuesta actual para generar otra.'))
        if self.proposal_id and self.proposal_id.state == 'draft':
            prop = self.proposal_id
        else:
            prop = Proposal.create({'case_id': self.id})
            self.proposal_id = prop.id
        prop._snapshot_from_calculadora(self.calculadora_id)
        self.write({'state': 'proposal_draft'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Propuesta'),
            'res_model': 'commercial.customer.proposal',
            'res_id': prop.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _sync_sale_order_from_calculadora(self):
        self.ensure_one()
        if not self.sale_order_id or not self.calculadora_id:
            return False
        calc = self.calculadora_id
        order = self.sale_order_id
        order.write({
            'calculator_projection_case_id': self.id,
            'calculator_projection_currency_id': calc.currency_id.id,
            'calculator_projection_total': calc.bridge_precio_final_cliente,
            'calculator_projection_24': calc._convert_from_company_currency(calc._calcular_escenario(plazo=24)['pago_mensual_total']),
            'calculator_projection_36': calc._convert_from_company_currency(calc._calcular_escenario(plazo=36)['pago_mensual_total']),
            'calculator_projection_48': calc._convert_from_company_currency(calc._calcular_escenario(plazo=48)['pago_mensual_total']),
            'calculator_projection_ready': True,
        })
        return True

    def _normalized_price_company_currency(self, po_line):
        self.ensure_one()
        company_currency = self.company_id.currency_id or self.env.company.currency_id
        po_currency = po_line.order_id.currency_id or company_currency
        date = po_line.order_id.date_order.date() if po_line.order_id.date_order else fields.Date.context_today(self)
        return po_currency._convert(
            po_line.price_unit or 0.0,
            company_currency,
            self.company_id,
            date,
            round=False,
        )

    def _sync_calculadora_from_alert_quotes(self, alert):
        """Sincroniza calculadora usando el mejor precio por producto entre cotizaciones de la alerta."""
        self.ensure_one()
        if not alert or not alert.purchase_order_ids:
            raise UserError(_('No hay cotizaciones para sincronizar la calculadora.'))

        quote_lines_by_product = {}
        for po in alert.purchase_order_ids:
            for po_line in po.order_line.filtered(lambda l: not l.display_type and l.product_id and l.product_id.type != 'service'):
                key = po_line.product_id.id
                current = quote_lines_by_product.get(key)
                current_normalized = self._normalized_price_company_currency(current) if current else 0.0
                new_normalized = self._normalized_price_company_currency(po_line)
                if not current or new_normalized < current_normalized:
                    quote_lines_by_product[key] = po_line

        if not quote_lines_by_product:
            raise UserError(_('No se encontraron líneas válidas de productos en las cotizaciones de la alerta.'))

        source_po = next(iter(quote_lines_by_product.values())).order_id
        calc = self._sync_calculadora_from_po(source_po)
        calc.line_ids.unlink()

        Line = self.env['calculadora.costos.line']
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        seq = 10
        for po_line in quote_lines_by_product.values():
            currency = po_line.order_id.currency_id or self.company_id.currency_id
            Line.create({
                'calculadora_id': calc.id,
                'sequence': seq,
                'name': po_line.name or po_line.product_id.display_name,
                'product_id': po_line.product_id.id,
                'product_qty': po_line.product_qty or 0.0,
                'price_unit': po_line.price_unit or 0.0,
                'moneda_equipo': 'USD' if usd and currency == usd else 'COP',
                'monto_garantia': 0.0,
            })
            seq += 10
        self.calculadora_id = calc.id
        self.write({'state': 'calculator_ready'})
        self.message_post(
            body=_('Calculadora sincronizada desde cotizaciones disponibles (mejor precio por producto).'),
        )
        return calc

    def _continue_flow_if_any_approval(self):
        """Continúa flujo operativo si hay propuesta aprobada o cotización ganadora aprobada."""
        self.ensure_one()
        proposal_ok = self.proposal_id and self.proposal_id.state == 'approved'
        quote_ok = self.winning_purchase_order_id and self.winning_purchase_order_id.approved_by_crm
        if not self._can_execute_operations(proposal_ok=proposal_ok, quote_ok=quote_ok):
            return False
        if not self.calculadora_id:
            return False
        if self.state not in ('operations_done', 'cancelled'):
            self.write({'state': 'customer_approved'})
        self._route_after_customer_approval()
        return True

    def _confirm_winning_purchase_order(self):
        self.ensure_one()
        po = self.winning_purchase_order_id
        if not po and self.purchase_alert_id:
            po = self.purchase_alert_id.purchase_order_ids.filtered(lambda p: p.approved_by_crm)[:1]
            if po:
                self.action_set_winning_purchase_order(po)
        if not po:
            raise UserError(_('No existe una cotización aprobada para confirmar la compra.'))
        if not po.approved_by_crm:
            raise UserError(_('La cotización seleccionada no está aprobada por CRM.'))
        if po.state in ('draft', 'sent', 'to approve'):
            po.button_confirm()
        return po

    def _can_execute_operations(self, proposal_ok=False, quote_ok=False):
        self.ensure_one()
        policy = self.company_id.integration_execution_policy or 'customer_approved'
        if policy == 'crm_quote_approved':
            return bool(quote_ok)
        if policy == 'either':
            return bool(proposal_ok or quote_ok)
        return bool(proposal_ok)

    def action_open_proposal(self):
        self.ensure_one()
        if not self.proposal_id:
            return self.action_generate_proposal()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Propuesta'),
            'res_model': 'commercial.customer.proposal',
            'res_id': self.proposal_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _route_after_customer_approval(self):
        self.ensure_one()
        if self.operations_routed:
            return
        if not self.warehouse_id:
            self.message_post(body=_('No hay almacén en el caso: no se ejecutó ruteo automático.'))
            self.operations_routed = True
            self.write({'state': 'operations_done'})
            return
        calc = self.calculadora_id
        if not calc:
            self.operations_routed = True
            self.write({'state': 'operations_done'})
            return

        location = self.warehouse_id.lot_stock_id
        if not location:
            raise UserError(_('El almacén no tiene ubicación de stock configurada.'))

        lines = calc.line_ids.filtered(
            lambda l: l.product_id and l.product_id.type in ('product', 'consu')
        )
        shortage = []
        for line in lines:
            needed = line.product_qty or 0.0
            if needed <= 0:
                continue
            try:
                quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                available = sum(quants.mapped('quantity'))
            except Exception as err:
                _logger.warning('Stock gather error %s', err)
                available = line.product_id.qty_available or 0.0
            if available + 1e-6 < needed:
                shortage.append((line.product_id, needed - max(available, 0.0)))

        if shortage:
            po = self._create_auto_purchase_for_shortage(shortage)
            if po:
                self.last_auto_purchase_id = po.id
                self.message_post(
                    body=_('Sin stock suficiente: se generó orden de compra %s.') % po.name,
                )
        else:
            picking = self._create_delivery_picking_reserved(lines)
            if picking:
                self.last_picking_id = picking.id
                self._create_warehouse_preparation_activity(picking)
                self.message_post(
                    body=_('Stock disponible: entrega %s creada y reservada; actividad de alistamiento generada.') % picking.name,
                )

        self.operations_routed = True
        self.write({'state': 'operations_done'})

    def _create_delivery_picking_reserved(self, calc_lines):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            _logger.warning('Case %s sin cliente: no se crea picking', self.name)
            return False
        customer_loc = partner.property_stock_customer
        if not customer_loc:
            customer_loc = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        if not customer_loc:
            return False
        picking_type = self.warehouse_id.out_type_id
        if not picking_type or not picking_type.default_location_src_id:
            return False
        picking_vals = {
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': customer_loc.id,
            'origin': '%s | %s' % (self.name, self.calculadora_id.name if self.calculadora_id else ''),
            'note': _('Generado por aprobación cliente (integración CRM–Calculadora).'),
        }
        picking = self.env['stock.picking'].create(picking_vals)
        for line in calc_lines:
            qty = line.product_qty or 0.0
            if qty <= 0:
                continue
            self.env['stock.move'].create({
                'name': line.name or line.product_id.display_name,
                'picking_id': picking.id,
                'picking_type_id': picking.picking_type_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': qty,
            })
        if picking.move_ids:
            picking.action_confirm()
            picking.action_assign()
        return picking

    def _create_auto_purchase_for_shortage(self, shortage_list):
        """shortage_list: list of (product.product, qty_missing)"""
        self.ensure_one()
        if not shortage_list:
            return False
        partner_supplier = False
        first_line_vals = []
        warehouse = self.warehouse_id
        if not warehouse.in_type_id:
            raise UserError(_('El almacén no tiene tipo de operación de entrada.'))
        for product, qty in shortage_list:
            if qty <= 0:
                continue
            seller = product._select_seller(
                partner_id=False,
                quantity=qty,
                date=fields.Date.today(),
                uom_id=product.uom_id,
            )
            if not seller:
                raise UserError(_('No hay proveedor configurado para el producto %s.') % product.display_name)
            if partner_supplier and partner_supplier != seller.partner_id:
                raise UserError(
                    _('Los productos faltantes tienen distintos proveedores; ajuste manualmente la compra.')
                )
            partner_supplier = seller.partner_id
            first_line_vals.append((0, 0, {
                'product_id': product.id,
                'product_qty': qty,
                'product_uom_id': product.uom_id.id,
                'price_unit': seller.price or product.standard_price,
                'date_planned': fields.Datetime.now(),
                'name': _('Faltante caso %s – %s') % (self.name, product.display_name),
            }))
        if not partner_supplier or not first_line_vals:
            return False
        po_vals = {
            'partner_id': partner_supplier.id,
            'picking_type_id': warehouse.in_type_id.id,
            'origin': self.name,
            'order_line': first_line_vals,
        }
        Purchase = self.env['purchase.order']
        if 'sale_order_ids' in Purchase._fields and self.sale_order_id:
            po_vals['sale_order_ids'] = [(4, self.sale_order_id.id)]
        return Purchase.create(po_vals)

    def _create_warehouse_preparation_activity(self, picking):
        group = self.env.ref('stock.group_stock_user', raise_if_not_found=False)
        users = group.users if group else self.env['res.users']
        activity_type = self.env['mail.activity.type'].search([('name', 'ilike', 'To Do')], limit=1)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([], limit=1)
        for user in users[:5]:
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get_id('stock.picking'),
                'res_id': picking.id,
                'activity_type_id': activity_type.id if activity_type else False,
                'user_id': user.id,
                'summary': _('Alistamiento / reserva: %s') % picking.name,
                'note': _('Reserva generada desde caso %s. Revise y complete el alistamiento.') % self.name,
                'date_deadline': fields.Date.today(),
            })
