# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommercialCustomerProposal(models.Model):
    _name = 'commercial.customer.proposal'
    _description = 'Propuesta comercial al cliente (snapshot)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nueva propuesta'))
    case_id = fields.Many2one(
        'commercial.integration.case',
        string='Caso integración',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='case_id.partner_id',
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('sent', 'Enviada'),
            ('approved', 'Aprobada por cliente'),
            ('rejected', 'Rechazada'),
            ('cancelled', 'Cancelada'),
        ],
        default='draft',
        tracking=True,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda cotización',
        required=True,
        default=lambda self: self.env.ref('base.COP', raise_if_not_found=False),
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda base compañía',
        related='case_id.company_id.currency_id',
        store=True,
        readonly=True,
    )
    applied_currency_rate = fields.Float(
        string='Tasa aplicada',
        readonly=True,
        copy=False,
    )
    snap_base_cop = fields.Monetary(string='Base cotización', currency_field='currency_id', readonly=True, copy=False)
    snap_iva_cop = fields.Monetary(string='IVA cotización', currency_field='currency_id', readonly=True, copy=False)
    snap_insurance_cop = fields.Monetary(string='Seguro cotización', currency_field='currency_id', readonly=True, copy=False)
    snap_total_customer_cop = fields.Monetary(string='Precio final cliente', currency_field='currency_id', readonly=True, copy=False)
    snap_monthly_cop = fields.Monetary(string='Cuota mensual', currency_field='currency_id', readonly=True, copy=False)
    snap_contract_total_cop = fields.Monetary(string='Total contrato estimado', currency_field='currency_id', readonly=True, copy=False)
    selected_term_months = fields.Selection(
        [('24', '24 meses'), ('36', '36 meses'), ('48', '48 meses')],
        string='Escenario elegido',
        help='Escenario seleccionado por el cliente para renting.',
    )
    selected_monthly_amount = fields.Monetary(
        string='Cuota mensual elegida',
        currency_field='currency_id',
        compute='_compute_selected_monthly_amount',
        store=True,
    )
    calculadora_id = fields.Many2one(
        'calculadora.costos',
        string='Calculadora origen',
        readonly=True,
        copy=False,
    )
    proposal_option_ids = fields.One2many(
        'commercial.customer.proposal.option',
        'proposal_id',
        string='Opciones de cotización',
        readonly=True,
        copy=False,
    )
    product_projection_ids = fields.One2many(
        'commercial.customer.proposal.product',
        'proposal_id',
        string='Proyección mensual por producto',
        readonly=True,
        copy=False,
    )
    sent_date = fields.Datetime(readonly=True, copy=False)
    customer_response_date = fields.Datetime(readonly=True, copy=False)

    @api.depends('selected_term_months', 'snap_total_customer_cop')
    def _compute_selected_monthly_amount(self):
        for rec in self:
            if rec.selected_term_months:
                term = int(rec.selected_term_months)
                rec.selected_monthly_amount = (rec.snap_total_customer_cop or 0.0) / term if term else 0.0
            else:
                rec.selected_monthly_amount = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('Nueva propuesta'):
                vals['name'] = self.env['ir.sequence'].next_by_code('commercial.customer.proposal') or _('Nueva propuesta')
        return super().create(vals_list)

    def _snapshot_from_calculadora(self, calc):
        self.ensure_one()
        if not calc:
            raise UserError(_('No hay calculadora para generar el snapshot.'))
        self.currency_id = calc.currency_id.id
        self.calculadora_id = calc.id
        self.applied_currency_rate = calc.applied_currency_rate
        self.snap_base_cop = calc.bridge_amount_before_tax
        self.snap_iva_cop = calc.bridge_tax_amount
        self.snap_insurance_cop = calc._convert_from_company_currency(calc.bridge_manual_insurance_cop)
        self.snap_total_customer_cop = calc.bridge_precio_final_cliente
        self.snap_monthly_cop = calc.quote_monthly_amount if calc.calculation_type == 'subscription' else 0.0
        self.snap_contract_total_cop = calc.quote_contract_total if calc.calculation_type == 'subscription' else self.snap_total_customer_cop
        self._sync_product_projections(calc)
        self._sync_options_from_quotes()

    def _sync_product_projections(self, calc):
        self.ensure_one()
        self.product_projection_ids.unlink()
        company_total = sum(calc.line_ids.mapped('subtotal_base_cop')) or 0.0
        ProductProjection = self.env['commercial.customer.proposal.product']
        for line in calc.line_ids.filtered(lambda l: l.product_id and (l.product_qty or 0.0) > 0):
            line_company_total = line.subtotal_base_cop or 0.0
            share = (line_company_total / company_total) if company_total else 0.0
            line_quote_total = (self.snap_total_customer_cop or 0.0) * share
            ProductProjection.create({
                'proposal_id': self.id,
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.display_name,
                'product_uom_qty': line.product_qty or 0.0,
                'monthly_24': line_quote_total / 24.0,
                'monthly_36': line_quote_total / 36.0,
                'monthly_48': line_quote_total / 48.0,
            })

    @api.model
    def _option_label_from_index(self, index):
        """Genera etiquetas tipo A..Z, AA..AZ, BA..."""
        n = (index or 0) + 1
        chars = []
        while n > 0:
            n, rem = divmod(n - 1, 26)
            chars.append(chr(65 + rem))
        return ''.join(reversed(chars))

    def _sync_options_from_quotes(self):
        self.ensure_one()
        self.proposal_option_ids.unlink()
        alert = self.case_id.purchase_alert_id
        if not alert:
            return
        quotes = alert.purchase_order_ids.filtered(lambda po: po.state != 'cancel')
        Option = self.env['commercial.customer.proposal.option']
        OptionLine = self.env['commercial.customer.proposal.option.line']

        for idx, po in enumerate(quotes.sorted(key=lambda p: (p.amount_total, p.id))):
            label = self._option_label_from_index(idx)
            option = Option.create({
                'proposal_id': self.id,
                'name': _('Opción %s') % label,
                'sequence': (idx + 1) * 10,
                'purchase_order_id': po.id,
            })
            for po_line in po.order_line.filtered(lambda l: not l.display_type and l.product_id):
                OptionLine.create({
                    'option_id': option.id,
                    'product_id': po_line.product_id.id,
                    'name': po_line.name or po_line.product_id.display_name,
                    'product_uom_qty': po_line.product_qty or 0.0,
                    'product_uom_id': po_line.product_uom_id.id or po_line.product_id.uom_id.id,
                    'price_unit': po_line.price_unit or 0.0,
                    'price_subtotal': po_line.price_subtotal or 0.0,
                })

    def action_send_proposal(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se puede enviar una propuesta en borrador.'))
            calc = rec.case_id.calculadora_id
            if not calc:
                raise UserError(_('El caso no tiene calculadora sincronizada.'))
            rec._snapshot_from_calculadora(calc)
            rec.write({'state': 'sent', 'sent_date': fields.Datetime.now()})
            rec.case_id.write({'state': 'proposal_sent'})
            rec.message_post(body=_('Propuesta enviada al cliente (snapshot congelado).'))

    def action_register_customer_approved(self):
        for rec in self:
            if rec.state != 'sent':
                raise UserError(_('Solo puede aprobar propuestas enviadas.'))
            if rec.product_projection_ids and not rec.selected_term_months:
                raise UserError(_('Debe seleccionar el escenario (24, 36 o 48 meses) antes de aprobar.'))
            rec.write({
                'state': 'approved',
                'customer_response_date': fields.Datetime.now(),
            })
            rec.case_id._confirm_winning_purchase_order()
            rec.case_id.write({'state': 'customer_approved'})
            rec.case_id._continue_flow_if_any_approval()
            rec.message_post(body=_('Cliente aprobó la propuesta. Se ejecutó el ruteo operativo.'))

    def action_register_customer_rejected(self):
        for rec in self:
            if rec.state != 'sent':
                raise UserError(_('Solo puede rechazar propuestas enviadas.'))
            rec.write({
                'state': 'rejected',
                'customer_response_date': fields.Datetime.now(),
            })
            rec.case_id.write({'state': 'customer_rejected'})
            rec.message_post(body=_('Cliente rechazó la propuesta.'))

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class CommercialCustomerProposalOption(models.Model):
    _name = 'commercial.customer.proposal.option'
    _description = 'Opción de propuesta comercial'
    _order = 'sequence asc, id asc'

    proposal_id = fields.Many2one(
        'commercial.customer.proposal',
        string='Propuesta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Opción', required=True)
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Cotización origen',
        required=True,
        ondelete='restrict',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        related='purchase_order_id.partner_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='purchase_order_id.currency_id',
        store=True,
        readonly=True,
    )
    amount_total = fields.Monetary(
        string='Total opción',
        related='purchase_order_id.amount_total',
        currency_field='currency_id',
        store=True,
        readonly=True,
    )
    option_line_ids = fields.One2many(
        'commercial.customer.proposal.option.line',
        'option_id',
        string='Ítems de la opción',
        readonly=True,
        copy=False,
    )


class CommercialCustomerProposalOptionLine(models.Model):
    _name = 'commercial.customer.proposal.option.line'
    _description = 'Ítem de opción de propuesta'
    _order = 'id asc'

    option_id = fields.Many2one(
        'commercial.customer.proposal.option',
        string='Opción',
        required=True,
        ondelete='cascade',
        index=True,
    )
    proposal_id = fields.Many2one(
        'commercial.customer.proposal',
        string='Propuesta',
        related='option_id.proposal_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(string='Descripción', required=True)
    product_uom_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    price_unit = fields.Monetary(
        string='Precio unitario',
        currency_field='currency_id',
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='option_id.currency_id',
        store=True,
        readonly=True,
    )


class CommercialCustomerProposalProduct(models.Model):
    _name = 'commercial.customer.proposal.product'
    _description = 'Proyección mensual por producto'
    _order = 'id asc'

    proposal_id = fields.Many2one(
        'commercial.customer.proposal',
        string='Propuesta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='proposal_id.currency_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(string='Descripción', required=True)
    product_uom_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure')
    monthly_24 = fields.Monetary(string='24 meses', currency_field='currency_id')
    monthly_36 = fields.Monetary(string='36 meses', currency_field='currency_id')
    monthly_48 = fields.Monetary(string='48 meses', currency_field='currency_id')
