# -*- coding: utf-8 -*-
from odoo import api, models

# Líneas de negocio permitidas en stock.lot → Servicio (serial / ruta).
STOCK_LOT_SERVICE_BUSINESS_LINE_NAMES = (
    'RENTING DE EQUIPOS',
    'COMOPRINT',
)


class SubscriptionSubscription(models.Model):
    _inherit = 'subscription.subscription'

    @api.model
    def _stock_lot_service_business_line_names_upper(self):
        return {n.strip().upper() for n in STOCK_LOT_SERVICE_BUSINESS_LINE_NAMES}

    @api.model
    def _product_business_line(self, product):
        if not product:
            return False
        bl = getattr(product, 'business_line_id', False)
        if bl:
            return bl
        tmpl = getattr(product, 'product_tmpl_id', False)
        if tmpl and getattr(tmpl, 'business_line_id', False):
            return tmpl.business_line_id
        return False

    @api.model
    def _product_matches_stock_lot_service_business_line(self, product):
        """Solo RENTING DE EQUIPOS y COMOPRINT (campo business_line_id del producto)."""
        if 'product.business.line' not in self.env:
            return True
        bl = self._product_business_line(product)
        if not bl:
            return False
        return (bl.name or '').strip().upper() in self._stock_lot_service_business_line_names_upper()

    @api.model
    def _iter_recurring_pricelist_items(self, pricelist, plan=None):
        """Reglas de la lista de precios en «Precios recurrentes» (plan_id definido)."""
        if not pricelist:
            return self.env['product.pricelist.item']

        PricelistItem = self.env['product.pricelist.item']
        if 'plan_id' not in PricelistItem._fields:
            return PricelistItem.browse()

        items = PricelistItem.browse()
        if getattr(pricelist, 'subscription_item_ids', None):
            items |= pricelist.subscription_item_ids
        if getattr(pricelist, 'item_ids', None):
            items |= pricelist.item_ids.filtered('plan_id')

        if plan:
            items = items.filtered(lambda i: i.plan_id and i.plan_id.id == plan.id)
        else:
            items = items.filtered('plan_id')
        return items

    @api.model
    def _product_from_recurring_pricelist_item(self, item):
        product = getattr(item, 'product_id', False) or False
        if product:
            return product
        tmpl = getattr(item, 'product_tmpl_id', False)
        if tmpl and getattr(tmpl, 'product_variant_ids', None):
            return tmpl.product_variant_ids[:1]
        return self.env['product.product']

    @api.model
    def get_recurring_service_products_for_partner(self, partner, plan=None):
        """Servicios (type=service) del cliente según su lista de precios y planes recurrentes."""
        Product = self.env['product.product']
        if not partner:
            return Product.browse()
        commercial = partner.commercial_partner_id or partner
        pricelist = commercial.property_product_pricelist
        if not pricelist:
            return Product.browse()

        products = Product.browse()
        for item in self._iter_recurring_pricelist_items(pricelist, plan=plan):
            product = self._product_from_recurring_pricelist_item(item)
            if not product or product.type != 'service':
                continue
            if not self._product_matches_stock_lot_service_business_line(product):
                continue
            products |= product
        return products
