# -*- coding: utf-8 -*-
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def name_search(self, name='', args=None, domain=None, limit=100, operator='ilike', order=None, **kwargs):
        """En el selector de Licencia (Servicio) del stock de proveedor, solo mostrar productos que son licencias del módulo."""
        # Asegurar que domain es lista de tuplas (el frontend a veces pasa algo no válido y Domain() falla con 'e')
        if isinstance(domain, list) and (not domain or isinstance(domain[0], (list, tuple))):
            search_domain = list(domain)
        else:
            search_domain = list(args or []) if isinstance(args, list) else []
        if self.env.context.get('license_provider_stock_select'):
            Template = self.env['license.template']
            license_product_ids = Template.search([]).mapped('product_id').ids
            if license_product_ids:
                search_domain = search_domain + [('id', 'in', license_product_ids)]
        # Odoo 16+: el parámetro es domain (no args)
        return super().name_search(name=name, domain=search_domain, operator=operator, limit=limit)
