# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.osv import expression

_ROUTE_WIZARD_PRODUCT_SPEC = {
    'display_name': {},
    'default_code': {},
}

_ROUTE_WIZARD_SEARCH_LIMIT = 80


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _delivery_route_wizard_product_domain(self, domain):
        wizard_id = self.env.context.get('delivery_route_wizard_id')
        if not wizard_id:
            return domain
        wizard = self.env['delivery.route.trigger.wizard'].browse(
            int(wizard_id)
        )
        if not wizard.exists():
            return domain
        product_ids = wizard.route_available_product_ids.ids
        if not product_ids:
            return [('id', '=', 0)]
        extra = [('id', 'in', product_ids)]
        return expression.AND([domain or [], extra])

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100, **kwargs):
        """Catálogo precalculado del wizard Procesar Ruta (evita dominio pesado)."""
        legacy_args = kwargs.pop('args', None)
        if legacy_args is not None and domain is None:
            domain = legacy_args
        kwargs.pop('order', None)

        domain = self._delivery_route_wizard_product_domain(domain)
        if domain == [('id', '=', 0)]:
            return []
        return super().name_search(name, domain, operator, limit)

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None,
    ):
        """Buscar más: solo campos ligeros y catálogo de la ruta (evita timeout)."""
        if self.env.context.get('delivery_route_wizard_id'):
            domain = self._delivery_route_wizard_product_domain(domain)
            if domain == [('id', '=', 0)]:
                return {'length': 0, 'records': []}
            specification = _ROUTE_WIZARD_PRODUCT_SPEC
            if limit is None or limit > _ROUTE_WIZARD_SEARCH_LIMIT:
                limit = _ROUTE_WIZARD_SEARCH_LIMIT
        return super().web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
