# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    """Extender stock.lot para mostrar licencias asignadas"""
    _inherit = 'stock.lot'

    # Todas las líneas license.equipment enlazadas a este serial (fuente única para recomputos)
    license_line_ids = fields.One2many(
        'license.equipment',
        'lot_id',
        string='Líneas de licencia (todas)',
        help='Relación técnica con todas las asignaciones de este serial.',
    )

    # Many2many calculado: misma regla que _equipment_tab_lines_for_lot (no confiar solo en dominio One2many en la vista web).
    license_equipment_ids = fields.Many2many(
        'license.equipment',
        string='Licencias Asignadas al Equipo',
        compute='_compute_license_equipment_ids',
        inverse='_inverse_license_equipment_ids',
        store=False,
        readonly=False,
        help='Filtrado en servidor para la pestaña Licencias del Equipo.',
    )

    license_user_ids = fields.Many2many(
        'license.equipment',
        string='Licencias Asignadas al Usuario',
        compute='_compute_license_user_ids',
        inverse='_inverse_license_user_ids',
        store=False,
        readonly=False,
        help='Listado del contacto «Usuario»: licencias de usuario ya asignadas. Use «Agregar asignación» '
             'para vincular una licencia contratada que aún no tenga este usuario.',
    )

    @api.depends(
        'license_line_ids',
        'license_line_ids.state',
        'license_line_ids.contact_id',
        'license_line_ids.license_id',
        'license_line_ids.license_id.applies_to_equipment',
        'license_line_ids.license_id.applies_to_user',
        'license_line_ids.assignment_id',
    )
    def _compute_license_equipment_ids(self):
        Le = self.env['license.equipment']
        for lot in self:
            lot.license_equipment_ids = Le._equipment_tab_lines_for_lot(lot)

    def _inverse_license_equipment_ids(self):
        """Quitar licencias de equipo desde el serial: historial + liberar cupo."""
        Le = self.env['license.equipment']
        for lot in self:
            before = Le._equipment_tab_lines_for_lot(lot)
            after = lot.license_equipment_ids
            removed = before - after
            if removed:
                removed.remove_from_assignment_list(source='manual_delete')

    def _inverse_license_user_ids(self):
        """Quitar licencias de usuario desde el serial: historial + liberar cupo."""
        Le = self.env['license.equipment']
        for lot in self:
            if not getattr(lot, 'related_partner_id', None):
                continue
            before = Le._user_tab_lines_for_lot(lot)
            after = lot.license_user_ids
            removed = before - after
            if removed:
                removed.remove_from_assignment_list(source='manual_delete')

    @api.depends('related_partner_id')
    def _compute_license_user_ids(self):
        Le = self.env['license.equipment']
        for lot in self:
            if not hasattr(lot, 'related_partner_id') or not lot.related_partner_id:
                lot.license_user_ids = False
                continue
            lot.license_user_ids = Le._user_tab_lines_for_lot(lot)

    def action_view_user_licenses(self):
        """Abrir vista de licencias asignadas al usuario relacionado"""
        self.ensure_one()

        if not hasattr(self, 'related_partner_id') or not self.related_partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Usuario'),
                    'message': _('Este equipo no tiene un usuario relacionado asignado.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        tab_ids = self.env['license.equipment']._user_tab_lines_for_lot(self).ids
        domain = [('id', 'in', tab_ids)] if tab_ids else [('id', 'in', [])]

        return {
            'name': _('Licencias del Usuario: %s') % self.related_partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_contact_id': self.related_partner_id.id,
            },
            'target': 'current',
        }

    def _get_license_scope_data(self):
        """Obtiene cliente/ubicación relevantes para filtrar licencias del lote actual."""
        self.ensure_one()
        forced_partner_id = self.env.context.get('force_license_partner_id')
        forced_location_id = self.env.context.get('force_license_location_id')
        if forced_partner_id or forced_location_id:
            return forced_partner_id or False, forced_location_id or False

        location_partner_id = False
        lot_location_id = False

        try:
            if hasattr(self, 'location_partner_id') and self.location_partner_id:
                location_partner_id = self.location_partner_id.id
        except Exception:
            pass

        try:
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', self.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], order='quantity desc, in_date desc', limit=1)
            if quant and quant.location_id:
                lot_location_id = quant.location_id.id
        except Exception:
            pass

        return location_partner_id, lot_location_id

    def action_manage_equipment_licenses(self):
        """Abre la gestión de licencias del equipo actual, permitiendo crear asignaciones."""
        self.ensure_one()
        location_partner_id, lot_location_id = self._get_license_scope_data()

        tab_ids = self.env['license.equipment']._equipment_tab_lines_for_lot(self).ids
        domain = [('id', 'in', tab_ids)] if tab_ids else [('id', 'in', [])]

        return {
            'name': _('Licencias del Equipo: %s') % (self.name or self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_lot_id': self.id,
                'default_contact_id': getattr(self, 'related_partner_id', False) and self.related_partner_id.id or False,
                'default_partner_id': location_partner_id or False,
                'default_location_id': lot_location_id or False,
            },
            'target': 'current',
        }

    def action_manage_user_licenses(self):
        """Abre la gestión de licencias del usuario del equipo, permitiendo crear asignaciones."""
        self.ensure_one()
        if not hasattr(self, 'related_partner_id') or not self.related_partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Usuario'),
                    'message': _('Este equipo no tiene un usuario relacionado asignado.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        location_partner_id, lot_location_id = self._get_license_scope_data()
        tab_ids = self.env['license.equipment']._user_tab_lines_for_lot(self).ids
        domain = [('id', 'in', tab_ids)] if tab_ids else [('id', 'in', [])]

        return {
            'name': _('Licencias del Usuario: %s') % self.related_partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_contact_id': self.related_partner_id.id,
                'default_lot_id': False,
                'default_partner_id': location_partner_id or False,
                'default_location_id': lot_location_id or False,
            },
            'target': 'current',
        }

    def _action_return_license_editor_form(self, license_tab_type=None):
        """Vuelve al formulario del serial en modal (p. ej. tras agregar licencias)."""
        self.ensure_one()
        tab_type = license_tab_type or self.env.context.get('license_tab_type') or 'equipment'
        if tab_type not in ('equipment', 'user'):
            tab_type = 'equipment'

        form_view = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
        ctx = {
            'active_id': self.id,
            'active_model': 'stock.lot',
            'default_lot_id': self.id,
            'form_view_initial_mode': 'edit',
            'license_tab_type': tab_type,
        }
        if self.env.context.get('force_license_partner_id'):
            ctx['force_license_partner_id'] = self.env.context['force_license_partner_id']
        if self.env.context.get('force_license_location_id'):
            ctx['force_license_location_id'] = self.env.context['force_license_location_id']
        if self.env.context.get('from_route_lot_editor'):
            ctx['from_route_lot_editor'] = True

        title = _('Editar Elementos Asociados - %s') % (self.name or '')
        if not ctx.get('from_route_lot_editor'):
            title = self.display_name

        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'stock.lot',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': form_view.id if form_view else False,
            'target': 'new',
            'context': ctx,
        }

    def action_open_license_assignment_pick_wizard(self):
        """Abre un wizard para seleccionar la asignación sin usar el dropdown inline.

        Esto evita el recorte del selector dentro de la grilla editable.
        """
        self.ensure_one()
        tab_type = self.env.context.get('license_tab_type') or 'equipment'

        if tab_type not in ('equipment', 'user'):
            tab_type = 'equipment'

        if tab_type == 'user' and not getattr(self, 'related_partner_id', False):
            raise UserError(_('Este equipo no tiene un usuario relacionado asignado.'))

        return {
            'name': _('Agregar Asignación de Licencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.assignment.pick.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_license_tab_type': tab_type,
                'force_license_partner_id': self.env.context.get('force_license_partner_id') or False,
                'force_license_location_id': self.env.context.get('force_license_location_id') or False,
                'from_route_lot_editor': self.env.context.get('from_route_lot_editor') or False,
            },
        }
