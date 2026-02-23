# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleSubscriptionPricing(models.Model):
    """Extiende sale.subscription.pricing para agregar campo de moneda y cantidad por cliente."""
    _inherit = 'sale.subscription.pricing'
    
    client_quantity = fields.Integer(
        string='Cantidad',
        compute='_compute_client_quantity',
        store=False,
        help='Cantidad total de este producto/servicio en suscripciones de clientes que usan esta lista de precios (entero).'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        domain=[('name', 'in', ['COP', 'USD'])],
        help='Moneda en la que se cobrará este precio recurrente. Solo se pueden seleccionar COP o USD. Si no se especifica, se usará la moneda de la lista de precios.',
        default=lambda self: self._get_default_currency(),
        readonly=False
    )
    
    def _compute_client_quantity(self):
        """Cantidad por cliente que usa esta pricelist.
        - Productos bienes (type product/consu): cantidad desde stock del cliente (lotes/seriales).
        - Servicios (type service): cantidad desde Productos Agrupados (servicio asociado al equipo).
        Siempre valor entero."""
        for rec in self:
            qty = 0
            if not rec.pricelist_id or not rec.product_template_id:
                rec.client_quantity = 0
                continue
            try:
                template = rec.product_template_id
                product_type = getattr(template, 'type', 'consu') or 'consu'

                # Clientes que usan esta lista; si solo hay una empresa, cantidad solo de esa empresa (igual que Inventario Kanban por cliente)
                all_partners = self.env['res.partner'].search([
                    ('property_product_pricelist', '=', rec.pricelist_id.id)
                ])
                if not all_partners:
                    rec.client_quantity = 0
                    continue
                companies = all_partners.filtered(lambda p: p.is_company)
                if len(companies) == 1:
                    # Solo la empresa (sin contactos) para coincidir con Inventario Kanban al abrir ese cliente
                    partners = companies
                else:
                    partners = all_partners
                if not partners:
                    rec.client_quantity = 0
                    continue

                # Productos bienes: cantidad desde inventario del cliente (cada bien puede tener servicio asociado)
                if product_type in ('product', 'consu'):
                    qty = self._client_quantity_goods(partners, template)
                else:
                    # Servicios: desde Productos Agrupados (agrupado por servicio)
                    qty = self._client_quantity_services(partners, template)
            except Exception:
                pass
            rec.client_quantity = int(qty)

    def _client_quantity_goods(self, partners, template):
        """Cantidad de producto bien: mismo alcance que Inventario (cliente + ubicación)."""
        Lot = self.env['stock.lot']
        if len(partners) == 1 and hasattr(partners, '_get_customer_inventory_domain'):
            try:
                domain = partners._get_customer_inventory_domain()
                domain = domain + [('product_id.product_tmpl_id', '=', template.id)]
                return len(Lot.search(domain))
            except Exception:
                pass
        all_lot_ids = []
        for partner in partners:
            all_lot_ids.extend(self._get_customer_lot_ids(partner))
        all_lot_ids = list(set(all_lot_ids))
        if not all_lot_ids:
            pass  # fall through to subscription/quants
        else:
            return len(Lot.search([
                ('id', 'in', all_lot_ids),
                ('product_id.product_tmpl_id', '=', template.id),
            ]))
        # Sin customer_id/ubicación: usar ubicaciones de suscripciones y quants
        if 'subscription.subscription' not in self.env:
            return 0
        subs = self.env['subscription.subscription'].search([
            ('partner_id', 'in', partners.ids),
            ('state', 'in', ('draft', 'active')),
            ('location_id', '!=', False),
        ])
        if not subs:
            return 0
        loc_ids = set()
        for sub in subs:
            loc_ids.add(sub.location_id.id)
            loc_ids.update(
                self.env['stock.location'].search([
                    ('id', 'child_of', sub.location_id.id)
                ]).ids
            )
        if not loc_ids:
            return 0
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', list(loc_ids)),
            ('product_id.product_tmpl_id', '=', template.id),
            ('quantity', '>', 0),
        ])
        return int(sum(quants.mapped('quantity')))

    def _get_customer_lot_ids(self, partner):
        """Misma lógica que Inventario del cliente: lotes por customer_id + por ubicación (property_stock_customer)."""
        Lot = self.env['stock.lot']
        Quant = self.env['stock.quant']
        lot_ids = []
        if 'customer_id' in Lot._fields:
            lot_ids.extend(Lot.search([('customer_id', '=', partner.id)]).ids)
        customer_location = getattr(partner, 'property_stock_customer', None)
        if customer_location:
            quants = Quant.search([
                ('location_id', '=', customer_location.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])
            lot_ids.extend(quants.mapped('lot_id').ids)
        return list(set(lot_ids))

    def _client_quantity_services(self, partners, template):
        """Cantidad de servicio: mismo alcance que Inventario (cliente + ubicación), agrupado por servicio."""
        Lot = self.env['stock.lot']
        if 'subscription_service_product_id' not in Lot._fields:
            return self._client_quantity_services_fallback(partners, template)
        # Usar el mismo conjunto de lotes que la vista Inventario (por cliente y por ubicación)
        if len(partners) == 1 and hasattr(partners, '_get_customer_inventory_domain'):
            try:
                domain = partners._get_customer_inventory_domain()
                domain = domain + [('subscription_service_product_id.product_tmpl_id', '=', template.id)]
                return len(Lot.search(domain))
            except Exception:
                pass
        all_lot_ids = []
        for partner in partners:
            all_lot_ids.extend(self._get_customer_lot_ids(partner))
        all_lot_ids = list(set(all_lot_ids))
        if not all_lot_ids:
            return 0
        lots = Lot.search([
            ('id', 'in', all_lot_ids),
            ('subscription_service_product_id.product_tmpl_id', '=', template.id),
        ])
        return len(lots)

    def _client_quantity_services_fallback(self, partners, template):
        """Fallback cuando no hay subscription_service_product_id en stock.lot."""
        if 'subscription.subscription' not in self.env or 'subscription.product.grouped' not in self.env:
            return 0
        subs = self.env['subscription.subscription'].search([
            ('partner_id', 'in', partners.ids),
            ('state', 'in', ('draft', 'active')),
        ])
        if not subs:
            return 0
        grouped = self.env['subscription.product.grouped'].search([
            ('subscription_id', 'in', subs.ids),
            ('product_id.product_tmpl_id', '=', template.id),
            ('quantity', '>', 0),
        ])
        return int(sum(grouped.mapped('quantity')))
    
    @api.model
    def _get_default_currency(self):
        """Obtiene la moneda por defecto desde la pricelist o la compañía."""
        # Si estamos en un contexto de creación desde pricelist
        if self.env.context.get('default_pricelist_id'):
            pricelist = self.env['product.pricelist'].browse(
                self.env.context['default_pricelist_id']
            )
            if pricelist and pricelist.currency_id:
                return pricelist.currency_id.id
        # Si ya tenemos pricelist_id asignado
        if hasattr(self, 'pricelist_id') and self.pricelist_id and self.pricelist_id.currency_id:
            return self.pricelist_id.currency_id.id
        return self.env.company.currency_id.id
