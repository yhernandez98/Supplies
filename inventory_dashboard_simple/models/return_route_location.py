# -*- coding: utf-8 -*-
"""Ubicaciones de destino para clasificación E4 de rutas de devolución."""

from odoo import api, models, _
from odoo.exceptions import UserError


class ReturnRouteLocation(models.AbstractModel):
    _name = 'return.route.location'
    _description = 'Ubicaciones destino — devolución E4'

    @api.model
    def _find_location_by_complete_name_fragment(self, fragment, usages=None):
        """Busca por ruta completa; por defecto solo internal."""
        if usages is None:
            usages = ('internal',)
        elif isinstance(usages, str):
            usages = (usages,)
        return self.env['stock.location'].sudo().search([
            ('complete_name', 'ilike', fragment),
            ('usage', 'in', list(usages)),
        ], limit=1)

    @api.model
    def _find_prebaja_location(self):
        """Supp/PreBaja (tránsito) — destino baja en clasificación E4."""
        Location = self.env['stock.location'].sudo()
        usages = ('internal', 'transit')
        for fragment in ('Supp/PreBaja', 'PreBaja'):
            loc = self._find_location_by_complete_name_fragment(fragment, usages=usages)
            if loc:
                return loc
        supp = Location.search([
            ('name', '=', 'Supp'),
            ('usage', 'in', ('view', 'internal')),
        ], limit=1)
        if not supp:
            supp = Location.search([
                ('complete_name', 'ilike', 'Supp'),
                ('usage', 'in', ('view', 'internal')),
            ], limit=1)
        if supp:
            return Location.search([
                ('location_id', '=', supp.id),
                ('name', 'ilike', 'PreBaja'),
                ('usage', 'in', list(usages)),
            ], limit=1)
        return Location.browse()

    @api.model
    def _find_repair_location(self):
        """Supp/Reparación puede estar como internal o transit (config. del almacén)."""
        Location = self.env['stock.location'].sudo()
        usages = ('internal', 'transit')
        for fragment in ('Supp/Reparación', 'Supp/Reparacion', 'Reparación', 'Reparacion'):
            loc = self._find_location_by_complete_name_fragment(fragment, usages=usages)
            if loc:
                return loc
        supp = Location.search([
            ('name', '=', 'Supp'),
            ('usage', 'in', ('view', 'internal')),
        ], limit=1)
        if not supp:
            supp = Location.search([
                ('complete_name', 'ilike', 'Supp'),
                ('usage', 'in', ('view', 'internal')),
            ], limit=1)
        if supp:
            return Location.search([
                ('location_id', '=', supp.id),
                ('name', 'ilike', 'Repar'),
                ('usage', 'in', list(usages)),
            ], limit=1)
        return Location.browse()

    @api.model
    def _supp_internal_parent(self):
        """Ubicación vista/padre bajo la que crear Garantía y Baja."""
        exist = self._find_location_by_complete_name_fragment('Supp/Existencias')
        if exist and exist.location_id:
            return exist.location_id
        supp = self.env['stock.location'].sudo().search([
            ('complete_name', 'ilike', 'Supp'),
            ('usage', 'in', ('view', 'internal')),
        ], limit=1)
        return supp

    @api.model
    def _get_or_create_child_location(self, parent, name, usage='internal'):
        if not parent:
            raise UserError(_('No se encontró la ubicación padre del almacén Supp.'))
        Location = self.env['stock.location'].sudo()
        child = Location.search([
            ('location_id', '=', parent.id),
            ('name', '=', name),
        ], limit=1)
        if child:
            return child
        return Location.create({
            'name': name,
            'location_id': parent.id,
            'usage': usage,
            'company_id': parent.company_id.id or self.env.company.id,
        })

    @api.model
    def get_return_e4_destination_locations(self):
        """Devuelve dict código → stock.location para el wizard E4."""
        exist = self._find_location_by_complete_name_fragment('Supp/Existencias')
        if not exist:
            exist = self.env['stock.location'].sudo().search([
                ('name', 'ilike', 'Existencias'),
            ], limit=1)
        repair = self._find_repair_location()

        parent = self._supp_internal_parent()
        garantia = self._find_location_by_complete_name_fragment('Supp/Garantía')
        if not garantia:
            garantia = self._get_or_create_child_location(parent, 'Garantía')

        prebaja = self._find_prebaja_location()

        if not exist:
            raise UserError(_(
                'No se encontró la ubicación «Supp/Existencias». '
                'Verifique la configuración del almacén Supp.'
            ))
        if not repair:
            raise UserError(_(
                'No se encontró «Supp/Reparación» bajo Supp '
                '(tipo interno o tránsito) para el destino Reparación en E4.'
            ))
        if not prebaja:
            raise UserError(_(
                'No se encontró «Supp/PreBaja» bajo Supp '
                '(tipo interno o tránsito) para el destino de baja en E4.'
            ))

        return {
            'stock': exist,
            'warranty': garantia,
            'repair': repair,
            'scrap_initial': prebaja,
        }

    @api.model
    def location_for_return_e4_destination_code(self, code):
        locations = self.get_return_e4_destination_locations()
        loc = locations.get(code)
        if not loc:
            raise UserError(_('Destino de clasificación no válido: %s') % code)
        return loc
