# -*- coding: utf-8 -*-
"""Control de facturación en ruta de entrega: visible en E3, bloqueo al validar E4."""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# En entrega no se exige exit_date (se define al devolver al cliente).
DELIVERY_BILLING_LOT_FIELDS = (
    ('subscription_service_product_id', 'Servicio'),
    ('active_subscription_id', 'Suscripción'),
    ('reining_plazo', 'Plazo Renting'),
    ('entry_date', 'Fecha Activación Renting'),
)


class StockPickingDeliveryBilling(models.Model):
    _inherit = 'stock.picking'

    invdash_delivery_billing_pending = fields.Boolean(
        string='Pendiente facturación (ruta entrega)',
        compute='_compute_invdash_delivery_billing_pending',
        store=True,
        index=True,
    )
    invdash_delivery_billing_summary = fields.Char(
        string='Resumen facturación',
        compute='_compute_invdash_delivery_billing_summary',
        store=True,
    )
    invdash_delivery_route_stage = fields.Integer(
        string='Etapa ruta',
        compute='_compute_invdash_delivery_route_stage',
        store=True,
        index=True,
    )

    @api.depends('origin')
    def _compute_invdash_delivery_route_stage(self):
        for picking in self:
            origin = (picking.origin or '').strip()
            if picking._is_route_wizard_origin(origin):
                picking.invdash_delivery_route_stage = picking._route_stage_from_origin(origin)
            else:
                picking.invdash_delivery_route_stage = 0

    def _origin_is_return_route(self):
        self.ensure_one()
        origin = (self.origin or '').lower()
        if 'devolucion' in origin or 'devolución' in origin:
            return True
        if hasattr(self, '_origin_indicates_devolucion_route'):
            return self._origin_indicates_devolucion_route()
        if hasattr(self, '_is_return_picking_type') and self._is_return_picking_type(self):
            return True
        return False

    def _picking_is_salida_to_transporte(self):
        """Etapa E3: Supp/Salida → Supp/Transporte."""
        self.ensure_one()
        if hasattr(self, '_picking_is_salida_transport_leg'):
            return self._picking_is_salida_transport_leg()
        if not self.location_id or not self.location_dest_id:
            return False
        src = (self.location_id.complete_name or '').lower()
        dest = (self.location_dest_id.complete_name or '').lower()
        return 'salida' in src and 'transporte' in dest

    def _picking_is_transporte_to_client(self):
        """Etapa E4 entrega: Supp/Transporte → ubicación de cliente."""
        self.ensure_one()
        if not self.location_dest_id:
            return False
        exist = self.env['stock.location'].sudo().search([
            ('complete_name', '=', 'Supp/Existencias'),
        ], limit=1)
        if exist:
            dest_ids = self.env['stock.location'].sudo().search([
                ('id', 'child_of', exist.id),
            ]).ids
            if self.location_dest_id.id in dest_ids:
                return False
        if not hasattr(self, '_is_client_stock_location'):
            return False
        if not self._is_client_stock_location(self.location_dest_id):
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if stage == 4:
            return True
        src = (self.location_id.complete_name or self.location_id.name or '').lower()
        return 'transporte' in src or 'transito' in src or 'tránsito' in src

    def _is_delivery_route_e3_picking(self):
        self.ensure_one()
        if self._origin_is_return_route():
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if self._is_route_wizard_origin(self.origin) and stage == 3:
            return True
        return self._picking_is_salida_to_transporte() and self._is_route_wizard_origin(self.origin)

    def _is_delivery_route_e4_picking(self):
        self.ensure_one()
        return self._is_delivery_route_e4_billing_gate()

    def _is_delivery_route_e4_billing_gate(self):
        """Albarán en el que se valida la entrega al cliente (E4) de una ruta de entrega."""
        self.ensure_one()
        if self._origin_is_return_route():
            return False
        if not self._is_route_wizard_origin(self.origin):
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if stage == 4:
            return True
        if self._picking_is_transporte_to_client():
            return True
        return False

    def _route_picking_for_stage(self, stage):
        self.ensure_one()
        chain = self._get_route_chain_pickings()
        if chain:
            found = chain.filtered(
                lambda p: p._route_stage_from_origin(p.origin or '') == stage
            )
            if found:
                return found[:1]
            if stage == 3:
                found = chain.filtered(lambda p: p._picking_is_salida_to_transporte())
                if found:
                    return found[:1]
            if stage == 4:
                found = chain.filtered(lambda p: p._picking_is_transporte_to_client())
                if found:
                    return found[:1]
        return self.env['stock.picking']

    def _billing_serial_lots(self):
        self.ensure_one()
        lots = self.env['stock.lot']
        for ml in self.move_line_ids:
            if not ml.lot_id or ml.product_id.tracking != 'serial':
                continue
            lots |= ml.lot_id
        if lots:
            return lots
        for move in self.move_ids:
            if move.product_id.tracking != 'serial':
                continue
            for ml in move.move_line_ids:
                if ml.lot_id:
                    lots |= ml.lot_id
        return lots

    def _delivery_billing_incomplete_lots(self):
        return self._billing_serial_lots().filtered(
            lambda lot: bool(lot.invdash_delivery_billing_missing_labels())
        )

    def _invdash_is_delivery_billing_menu_candidate(self):
        """True si debe aparecer en Consultas → Facturación."""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            return False
        if self._origin_is_return_route():
            return False
        if not self._is_route_wizard_origin(self.origin):
            return False
        if not self._delivery_billing_incomplete_lots():
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if stage in (3, 4):
            return True
        if self._is_delivery_route_e3_picking():
            return True
        if self._is_delivery_route_e4_billing_gate():
            return True
        return False

    @api.model
    def _search_delivery_billing_pending(self):
        candidates = self.search([
            ('state', 'not in', ('done', 'cancel')),
            '|',
            ('origin', '=like', 'Ruta-%'),
            ('origin', '=like', 'Ruta:%'),
        ])
        return candidates.filtered(lambda p: p._invdash_is_delivery_billing_menu_candidate())

    def _delivery_billing_missing_messages(self):
        self.ensure_one()
        lines = []
        for lot in self._delivery_billing_incomplete_lots():
            missing = lot.invdash_delivery_billing_missing_labels()
            if missing:
                label = lot.inventory_plate or lot.name or lot.display_name
                lines.append('%s: %s' % (label, ', '.join(missing)))
        return lines

    def _check_delivery_route_e4_billing_before_validate(self):
        for picking in self:
            if picking.state in ('done', 'cancel'):
                continue
            if not picking._is_delivery_route_e4_billing_gate():
                continue
            e3 = picking._route_picking_for_stage(3)
            if e3 and e3.state != 'done':
                raise UserError(_(
                    'No puede validar la entrega al cliente (etapa E4) hasta validar antes '
                    'el traslado Salida → Transporte (etapa E3): %s.'
                ) % (e3.display_name or e3.name))
            missing_lines = picking._delivery_billing_missing_messages()
            if missing_lines:
                body = '\n'.join(missing_lines[:25])
                if len(missing_lines) > 25:
                    body += '\n…'
                raise UserError(_(
                    'No puede validar la etapa E4 (Transporte → cliente) hasta completar en cada '
                    'serial: Servicio, Suscripción, Plazo Renting y Fecha Activación Renting.\n\n%s'
                ) % body)

    def button_validate(self):
        self._check_delivery_route_e4_billing_before_validate()
        res = super().button_validate()
        try:
            self.filtered(lambda p: p.state == 'done')._run_return_route_client_cleanup()
        except Exception as exc:
            _logger.warning(
                'Error en limpieza automática tras ruta de devolución: %s', exc,
            )
        return res

    def _action_done(self):
        self._check_delivery_route_e4_billing_before_validate()
        res = super()._action_done()
        return res

    @api.depends(
        'state',
        'origin',
        'location_id',
        'location_dest_id',
        'move_line_ids',
        'move_line_ids.lot_id',
        'move_line_ids.lot_id.subscription_service_product_id',
        'move_line_ids.lot_id.active_subscription_id',
        'move_line_ids.lot_id.reining_plazo',
        'move_line_ids.lot_id.entry_date',
    )
    def _compute_invdash_delivery_billing_pending(self):
        for picking in self:
            picking.invdash_delivery_billing_pending = (
                picking._invdash_is_delivery_billing_menu_candidate()
            )

    @api.depends('invdash_delivery_billing_pending', 'origin')
    def _compute_invdash_delivery_billing_summary(self):
        for picking in self:
            if not picking.invdash_delivery_billing_pending:
                picking.invdash_delivery_billing_summary = ''
                continue
            n_lots = len(picking._delivery_billing_incomplete_lots())
            stage = picking.invdash_delivery_route_stage or picking._route_stage_from_origin(
                picking.origin or ''
            )
            picking.invdash_delivery_billing_summary = _('E%s: %s serial(es) incompleto(s)') % (
                stage or '?', n_lots,
            )

    @api.model
    def domain_delivery_route_billing_pending(self):
        ids = self._search_delivery_billing_pending().ids
        if ids:
            return [('id', 'in', ids)]
        return [('id', '=', 0)]

    @api.model
    def delivery_route_billing_pending_count(self):
        return len(self._search_delivery_billing_pending())

    def action_open_delivery_billing_lots(self):
        self.ensure_one()
        lots = self._delivery_billing_incomplete_lots() or self._billing_serial_lots()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seriales — %s') % (self.display_name or self.name),
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', lots.ids)],
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_open_delivery_billing_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            chains = self.env['stock.picking']
            for picking in self.filtered(
                lambda p: p._is_route_wizard_origin(p.origin)
            ):
                chains |= picking._get_route_chain_pickings()
            if chains:
                chains._compute_invdash_delivery_billing_pending()
        return res

    @api.model
    def _recompute_all_delivery_billing_pending(self):
        """Recalcula pendientes (p. ej. tras actualizar el módulo)."""
        candidates = self.search([
            '|',
            ('origin', '=like', 'Ruta-%'),
            ('origin', '=like', 'Ruta:%'),
        ])
        if candidates:
            candidates._compute_invdash_delivery_route_stage()
            candidates._compute_invdash_delivery_billing_pending()
            candidates._compute_invdash_delivery_billing_summary()
        return len(candidates.filtered(lambda p: p.invdash_delivery_billing_pending))

    @api.model
    def action_open_delivery_billing_refreshed(self):
        self._recompute_all_delivery_billing_pending()
        action = self.env.ref(
            'inventory_dashboard_simple.action_delivery_route_billing_pending'
        ).read()[0]
        action['domain'] = self.domain_delivery_route_billing_pending()
        action['views'] = [
            (self.env.ref(
                'inventory_dashboard_simple.view_delivery_route_billing_picking_list'
            ).id, 'list'),
            (self.env.ref('stock.view_picking_form').id, 'form'),
        ]
        return action


class StockLotDeliveryBilling(models.Model):
    _inherit = 'stock.lot'

    invdash_delivery_billing_complete = fields.Boolean(
        string='Facturación completa (ruta entrega)',
        compute='_compute_invdash_delivery_billing_complete',
        store=True,
        index=True,
    )

    @api.depends(
        'subscription_service_product_id',
        'active_subscription_id',
        'reining_plazo',
        'entry_date',
    )
    def _compute_invdash_delivery_billing_complete(self):
        for lot in self:
            lot.invdash_delivery_billing_complete = lot._invdash_delivery_billing_fields_complete()

    def _invdash_delivery_billing_fields_complete(self):
        self.ensure_one()
        return not bool(self.invdash_delivery_billing_missing_labels())

    def invdash_delivery_billing_missing_labels(self):
        self.ensure_one()
        missing = []
        for field_name, label in DELIVERY_BILLING_LOT_FIELDS:
            if field_name not in self._fields:
                continue
            if not self[field_name]:
                missing.append(label)
        return missing

    def write(self, vals):
        res = super().write(vals)
        billing_fields = {f[0] for f in DELIVERY_BILLING_LOT_FIELDS}
        if billing_fields.intersection(vals.keys()):
            pickings = self.env['stock.picking'].search([
                ('move_line_ids.lot_id', 'in', self.ids),
                ('state', 'not in', ('done', 'cancel')),
                '|',
                ('origin', '=like', 'Ruta-%'),
                ('origin', '=like', 'Ruta:%'),
            ])
            if pickings:
                pickings._compute_invdash_delivery_billing_pending()
        return res
