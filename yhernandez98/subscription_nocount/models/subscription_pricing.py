# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleSubscriptionPricing(models.Model):
    """Extiende sale.subscription.pricing para agregar campo de moneda."""
    _inherit = 'sale.subscription.pricing'
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        domain=[('name', 'in', ['COP', 'USD'])],
        help='Moneda en la que se cobrará este precio recurrente. Solo se pueden seleccionar COP o USD. Si no se especifica, se usará la moneda de la lista de precios.',
        default=lambda self: self._get_default_currency(),
        readonly=False
    )
    
    @api.model
    def _get_default_currency(self):
        """Obtiene la moneda por defecto desde la pricelist o la compañía."""
        # Si estamos en un contexto de creación desde pricelist
        if self.env.context.get('default_pricelist_id'):
            pricelist = self.env['product.pricelist'].browse(self.env.context['default_pricelist_id'])
            if pricelist and pricelist.currency_id:
                return pricelist.currency_id.id
        # Si ya tenemos pricelist_id asignado
        if hasattr(self, 'pricelist_id') and self.pricelist_id and self.pricelist_id.currency_id:
            return self.pricelist_id.currency_id.id
        return self.env.company.currency_id.id
