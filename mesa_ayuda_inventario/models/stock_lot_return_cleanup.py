# -*- coding: utf-8 -*-
"""Limpieza de serial al salir del inventario del cliente (ruta de devolución, etapa E1)."""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class StockLotReturnCleanup(models.Model):
    _inherit = 'stock.lot'

    def _return_route_equipment_license_lines(self):
        """Misma fuente que «Licencias del Equipo» / retiro en Mesa de Ayuda (solo tipo equipo)."""
        self.ensure_one()
        if 'license.equipment' not in self.env:
            return self.env['license.equipment'].browse()
        LE = self.env['license.equipment'].sudo()
        if hasattr(LE, '_equipment_tab_lines_for_lot'):
            return LE._equipment_tab_lines_for_lot(self).filtered(lambda r: r.state == 'assigned')
        if hasattr(self, 'license_equipment_ids'):
            return self.license_equipment_ids.filtered(
                lambda r: r.state == 'assigned' and not r.contact_id
            )
        return LE.search([
            ('lot_id', '=', self.id),
            ('state', '=', 'assigned'),
            ('contact_id', '=', False),
        ])

    def _return_route_withdraw_equipment_licenses(self, picking_label=None):
        """Retiro de licencias de equipo con historial (misma lógica que Mesa de Ayuda)."""
        self.ensure_one()
        lines = self._return_route_equipment_license_lines()
        if not lines:
            return 0
        label = picking_label or _('Ruta de devolución')
        lines.remove_from_assignment_list(
            source='mesa_retiro',
            helpdesk_ticket_name=label,
        )
        _logger.info(
            'Ruta devolución: retiradas %s licencia(s) de equipo del lote %s (%s)',
            len(lines), self.name, label,
        )
        return len(lines)

    def cleanup_after_return_from_client_location(self, picking=None):
        """Limpia suscripción, servicio, usuario, fechas renting y código de facturación.

        Debe ejecutarse después de marcar exit_date (salida desde cliente). Al quitar la
        suscripción se conservan last_* / pending_removal_date para el facturable hasta día 1.
        """
        self.ensure_one()
        picking_label = False
        if picking:
            picking_label = picking.display_name or picking.name or picking.origin

        lic_count = self._return_route_withdraw_equipment_licenses(picking_label=picking_label)

        vals = {}
        if 'active_subscription_id' in self._fields and self.active_subscription_id:
            vals['active_subscription_id'] = False
        if 'subscription_service_product_id' in self._fields and self.subscription_service_product_id:
            vals['subscription_service_product_id'] = False
        if 'related_partner_id' in self._fields and self.related_partner_id:
            vals['related_partner_id'] = False
        if 'entry_date' in self._fields and self.entry_date:
            vals['entry_date'] = False
        if 'exit_date' in self._fields and self.exit_date:
            vals['exit_date'] = False
        if 'billing_code' in self._fields and self.billing_code:
            vals['billing_code'] = False
        if 'reining_plazo' in self._fields and self.reining_plazo:
            vals['reining_plazo'] = False
        if 'reining_plazo_custom_months' in self._fields and self.reining_plazo_custom_months:
            vals['reining_plazo_custom_months'] = 0

        if vals:
            self.sudo().write(vals)
            _logger.info(
                'Ruta devolución: limpieza de lote %s (%s campos; %s licencia(s) retiradas)',
                self.name, len(vals), lic_count,
            )
        elif lic_count:
            _logger.info(
                'Ruta devolución: solo licencias en lote %s (%s retiradas)',
                self.name, lic_count,
            )
        return bool(vals) or bool(lic_count)
