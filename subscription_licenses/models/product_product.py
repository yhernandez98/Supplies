# -*- coding: utf-8 -*-
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None, **kwargs):
        """En el selector de Licencia (Servicio) del stock de proveedor, solo licencias del módulo."""
        domain = list(domain or [])
        if self.env.context.get('license_provider_stock_select'):
            rows = self.env['license.template'].sudo().search_read([], ['product_id'])
            license_product_ids = list(
                {
                    row['product_id'][0]
                    for row in rows
                    if row.get('product_id') and row['product_id'][0]
                }
            )
            if license_product_ids:
                domain = domain + [('id', 'in', license_product_ids)]
        return super()._name_search(
            name, domain=domain, operator=operator, limit=limit, order=order, **kwargs
        )
