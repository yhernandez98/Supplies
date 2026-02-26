# -*- coding: utf-8 -*-
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def name_search(self, name='', args=None, domain=None, limit=100, operator='ilike', order=None, **kwargs):
        """En el selector de Licencia (Servicio) del stock de proveedor, solo mostrar productos que son licencias del módulo."""
        search_domain = list(domain if domain is not None else (args or []))
        if self.env.context.get('license_provider_stock_select'):
            Template = self.env['license.template']
            license_product_ids = Template.search([]).mapped('product_id').ids
            if license_product_ids:
                search_domain = search_domain + [('id', 'in', license_product_ids)]
        # Odoo 16+: el parámetro es domain (no args)
        return super().name_search(name=name, domain=search_domain, operator=operator, limit=limit)
