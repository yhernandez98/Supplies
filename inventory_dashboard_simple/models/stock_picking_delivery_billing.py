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

# Placas obligatorias al validar E2 (Alistamiento → Salida).
DELIVERY_E2_LOT_FIELDS = (
    ('inventory_plate', 'Placa de Inventario'),
    ('security_plate', 'Placa de Seguridad'),
)

# Productos con estas clasificaciones (product_suppiles) NO requieren los datos de
# facturación al validar E4. UPS es la excepción: aunque esté clasificado, sí se exigen.
DELIVERY_BILLING_EXEMPT_CLASSIFICATIONS = frozenset({
    'component',   # Componente
    'peripheral',  # Periférico
    'complement',  # Complemento
    'monitor',     # Monitores
    'spare',       # Repuestos
})


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
    invdash_delivery_route_stage_label = fields.Char(
        string='Etapa ruta (etiqueta)',
        compute='_compute_invdash_delivery_route_stage_label',
    )

    @api.depends('origin', 'location_id', 'location_dest_id')
    def _compute_invdash_delivery_route_stage(self):
        for picking in self:
            if picking._origin_is_return_route() and hasattr(
                picking, '_infer_return_route_stage_from_locations'
            ):
                return_stage = picking._infer_return_route_stage_from_locations()
                if return_stage:
                    picking.invdash_delivery_route_stage = return_stage
                    continue
            by_location = picking._infer_delivery_route_stage_from_locations()
            if by_location:
                picking.invdash_delivery_route_stage = by_location
                continue
            origin = (picking.origin or '').strip()
            if picking._is_route_wizard_origin(origin):
                picking.invdash_delivery_route_stage = picking._route_stage_from_origin(origin)
            else:
                picking.invdash_delivery_route_stage = 0

    @api.depends('invdash_delivery_route_stage', 'origin', 'location_id', 'location_dest_id')
    def _compute_invdash_delivery_route_stage_label(self):
        stage_titles = {
            1: _('E1 — Existencias → Alistamiento'),
            2: _('E2 — Alistamiento → Salida'),
            3: _('E3 — Salida → Transporte'),
            4: _('E4 — Transporte → Cliente'),
        }
        for picking in self:
            stage = picking.invdash_delivery_route_stage
            if not stage:
                stage = picking._infer_delivery_route_stage_from_locations()
            if picking._origin_is_return_route():
                return_titles = {
                    1: _('E1 — Cliente → Transporte'),
                    2: _('E2 — Transporte → Devolución'),
                    3: _('E3 — Devolución → Verificación'),
                    4: _('E4 — Verificación → clasificar destinos'),
                }
                picking.invdash_delivery_route_stage_label = return_titles.get(stage, '')
            else:
                picking.invdash_delivery_route_stage_label = stage_titles.get(stage, '')

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

    def _picking_is_existencias_to_alistamiento(self):
        """Etapa E1: Supp/Existencias → Supp/Alistamiento."""
        self.ensure_one()
        if not self.location_id or not self.location_dest_id:
            return False
        src = (self.location_id.complete_name or '').lower()
        dest = (self.location_dest_id.complete_name or '').lower()
        return 'existencias' in src and 'alistamiento' in dest

    def _picking_is_alistamiento_to_salida(self):
        """Etapa E2: Supp/Alistamiento → Supp/Salida."""
        self.ensure_one()
        if not self.location_id or not self.location_dest_id:
            return False
        src = (self.location_id.complete_name or '').lower()
        dest = (self.location_dest_id.complete_name or '').lower()
        return 'alistamiento' in src and 'salida' in dest

    def _infer_delivery_route_stage_from_locations(self):
        """Etapa por ubicaciones (ruta automática desde pedido, sin origin Ruta-…-E#)."""
        self.ensure_one()
        if self._picking_is_existencias_to_alistamiento():
            return 1
        if self._picking_is_alistamiento_to_salida():
            return 2
        if self._picking_is_salida_to_transporte():
            return 3
        if self._picking_is_transporte_to_client():
            return 4
        return 0

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

    def _is_delivery_route_e1_picking(self):
        """Albarán E1 de ruta de entrega: Existencias → Alistamiento."""
        self.ensure_one()
        if self._origin_is_return_route():
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if self._is_route_wizard_origin(self.origin) and stage == 1:
            return True
        return self._picking_is_existencias_to_alistamiento()

    def _is_delivery_route_e2_picking(self):
        """Albarán E2 de ruta de entrega: Alistamiento → Salida."""
        self.ensure_one()
        if self._origin_is_return_route():
            return False
        stage = self._route_stage_from_origin(self.origin or '')
        if self._is_route_wizard_origin(self.origin) and stage == 2:
            return True
        return self._picking_is_alistamiento_to_salida()

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

    def _delivery_e2_plates_incomplete_lots(self):
        return self._billing_serial_lots().filtered(
            lambda lot: bool(lot.invdash_e2_plates_missing_labels())
        )

    def _delivery_e2_plates_missing_messages(self):
        self.ensure_one()
        lines = []
        for lot in self._delivery_e2_plates_incomplete_lots():
            missing = lot.invdash_e2_plates_missing_labels()
            if missing:
                label = lot.name or lot.display_name
                lines.append('%s: %s' % (label, ', '.join(missing)))
        return lines

    def _is_delivery_route_e3_billing_menu_picking(self):
        """Solo albarán E3 (Salida → Transporte) de ruta de entrega — menú Facturación."""
        self.ensure_one()
        if self._origin_is_return_route():
            return False
        if self._picking_is_transporte_to_client():
            return False
        stage_loc = self._infer_delivery_route_stage_from_locations()
        if stage_loc and stage_loc != 3:
            return False
        origin = (self.origin or '').strip()
        stage_origin = self._route_stage_from_origin(origin)
        if self._is_route_wizard_origin(origin):
            return stage_origin == 3
        if stage_origin == 3:
            return True
        return bool(stage_loc == 3 and self._picking_is_salida_to_transporte())

    def _invdash_is_delivery_billing_menu_candidate(self):
        """True si debe aparecer en Consultas → Facturación (solo E3)."""
        self.ensure_one()
        if not self.id:
            return False
        if self.state in ('done', 'cancel'):
            return False
        if not self._delivery_billing_incomplete_lots():
            return False
        return self._is_delivery_route_e3_billing_menu_picking()

    @api.model
    def _search_delivery_billing_pending(self):
        candidates = self.search([
            ('state', 'not in', ('done', 'cancel')),
            ('origin', '=like', 'Ruta%'),
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

    def _delivery_route_validation_wizard_action(self, validation_type, messages):
        self.ensure_one()
        wizard = self.env['delivery.route.validation.wizard'].create({
            'picking_id': self.id,
            'validation_type': validation_type,
            'line_ids': [(0, 0, {'detail': msg}) for msg in messages[:50]],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Validación ruta de entrega'),
            'res_model': 'delivery.route.validation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _delivery_route_pre_validate_action(self):
        """Abre wizard aqua si faltan datos; si no, None."""
        for picking in self:
            if picking.state in ('done', 'cancel'):
                continue
            if picking._is_delivery_route_e4_billing_gate():
                e3 = picking._route_picking_for_stage(3)
                if e3 and e3.state != 'done':
                    return picking._delivery_route_validation_wizard_action(
                        'e4_e3_pending',
                        [_('Albarán E3 pendiente: %s') % (e3.display_name or e3.name)],
                    )
            if picking._is_delivery_route_e2_picking():
                missing = picking._delivery_e2_plates_missing_messages()
                if missing:
                    return picking._delivery_route_validation_wizard_action('e2_plates', missing)
            if picking._is_delivery_route_e4_billing_gate():
                missing = picking._delivery_billing_missing_messages()
                if missing:
                    return picking._delivery_route_validation_wizard_action('e4_billing', missing)
        return None

    def _check_delivery_route_e2_plates_before_validate(self):
        for picking in self:
            if picking.state in ('done', 'cancel'):
                continue
            if not picking._is_delivery_route_e2_picking():
                continue
            missing_lines = picking._delivery_e2_plates_missing_messages()
            if missing_lines:
                body = '\n'.join(missing_lines[:25])
                if len(missing_lines) > 25:
                    body += '\n…'
                raise UserError(_(
                    'No puede validar la etapa E2 (Alistamiento → Salida) hasta completar en '
                    'cada serial: Placa de Inventario y Placa de Seguridad.\n\n%s'
                ) % body)

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
        e4_classify = self._return_route_e4_pre_validate_action()
        if e4_classify:
            return e4_classify
        block = self._delivery_route_pre_validate_action()
        if block:
            return block
        self._check_delivery_route_e2_plates_before_validate()
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
        self._check_delivery_route_e2_plates_before_validate()
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
        if self:
            self.mapped('state')
        for picking in self:
            if not picking.id:
                picking.invdash_delivery_billing_pending = False
                continue
            try:
                picking.invdash_delivery_billing_pending = (
                    picking._invdash_is_delivery_billing_menu_candidate()
                )
            except Exception as exc:
                _logger.warning(
                    'No se pudo calcular invdash_delivery_billing_pending para %s: %s',
                    picking.display_name,
                    exc,
                )
                picking.invdash_delivery_billing_pending = False

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

    def _delivery_route_stage_for_lot_context(self):
        """Etapa E# de la ruta para pasar al editor de serial (modal desde albarán)."""
        self.ensure_one()
        by_location = self._infer_delivery_route_stage_from_locations()
        if by_location:
            return by_location
        if self.invdash_delivery_route_stage:
            return self.invdash_delivery_route_stage
        return self._route_stage_from_origin(self.origin or '') or 0

    def _delivery_route_lot_form_context(self):
        """Contexto al abrir el serial desde un albarán de ruta."""
        self.ensure_one()
        stage = self._delivery_route_stage_for_lot_context()
        return {
            'from_route_lot_editor': True,
            'delivery_route_stage': stage,
            'hide_delivery_e3_billing_fields': stage in (1, 2),
            'route_editor_picking_id': self.id,
        }

    def action_open_delivery_billing_lots(self):
        self.ensure_one()
        lots = self._delivery_billing_incomplete_lots() or self._billing_serial_lots()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seriales — %s') % (self.display_name or self.name),
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', lots.ids)],
            'context': dict(
                {'form_view_initial_mode': 'edit'},
                **self._delivery_route_lot_form_context(),
            ),
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
                chains.invalidate_recordset([
                    'invdash_delivery_billing_pending',
                    'invdash_delivery_billing_summary',
                ])
        return res

    @api.model
    def _recompute_all_delivery_billing_pending(self):
        """Recalcula pendientes (p. ej. tras actualizar el módulo)."""
        candidates = self.search([('origin', '=like', 'Ruta%')])
        if candidates:
            candidates._compute_invdash_delivery_route_stage()
            candidates._compute_invdash_delivery_billing_pending()
            candidates._compute_invdash_delivery_billing_summary()
        return len(candidates.filtered(lambda p: p.invdash_delivery_billing_pending))

    @api.model
    def action_open_delivery_billing_refreshed(self):
        """Abre Facturación sin leer ir.actions.act_window como el usuario (Odoo 19)."""
        self._recompute_all_delivery_billing_pending()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'inventory_dashboard_simple.action_delivery_route_billing_pending'
        )
        action['domain'] = self.domain_delivery_route_billing_pending()
        action['views'] = [
            (self.env.ref(
                'inventory_dashboard_simple.view_delivery_route_billing_picking_list'
            ).sudo().id, 'list'),
            (self.env.ref('stock.view_picking_form').sudo().id, 'form'),
        ]
        return action


class StockLotDeliveryBilling(models.Model):
    _inherit = 'stock.lot'

    show_delivery_route_e3_billing_fields = fields.Boolean(
        string='Mostrar campos facturación (E3+)',
        compute='_compute_show_delivery_route_e3_billing_fields',
    )
    show_delivery_route_cost_fields = fields.Boolean(
        string='Mostrar campos de costo (E3+)',
        compute='_compute_show_delivery_route_cost_fields',
    )
    show_delivery_route_e1_minimal_form = fields.Boolean(
        string='Formulario reducido E1',
        compute='_compute_show_delivery_route_e1_minimal_form',
    )
    # Obsoleto: se mantiene por compatibilidad con vistas XML antiguas en servidor.
    # Siempre False: en E2 deben verse elementos asociados y licencias.
    show_delivery_route_e2_plates_form = fields.Boolean(
        string='Formulario reducido E2 (obsoleto)',
        compute='_compute_show_delivery_route_e2_plates_form',
    )

    invdash_delivery_billing_complete = fields.Boolean(
        string='Facturación completa (ruta entrega)',
        compute='_compute_invdash_delivery_billing_complete',
        store=True,
        index=True,
    )

    @staticmethod
    def _delivery_route_lot_editor_stage_from_context(env):
        if not (
            env.context.get('from_route_lot_editor')
            or env.context.get('route_editor_picking_id')
        ):
            return 0
        try:
            stage = int(env.context.get('delivery_route_stage') or 0)
        except (TypeError, ValueError):
            stage = 0
        if stage:
            return stage
        picking_id = env.context.get('route_editor_picking_id')
        if picking_id:
            picking = env['stock.picking'].browse(picking_id)
            if picking.exists():
                return picking._delivery_route_stage_for_lot_context()
        return 0

    @staticmethod
    def _delivery_route_lot_visibility_flags(env):
        """Flags de visibilidad del serial según etapa E# (modal desde albarán)."""
        if not (
            env.context.get('from_route_lot_editor')
            or env.context.get('route_editor_picking_id')
        ):
            return {
                'show_delivery_route_e3_billing_fields': True,
                'show_delivery_route_cost_fields': True,
                'show_delivery_route_e1_minimal_form': False,
            }
        stage = StockLotDeliveryBilling._delivery_route_lot_editor_stage_from_context(env)
        if env.context.get('hide_delivery_e3_billing_fields'):
            show_billing = False
        else:
            show_billing = stage >= 3
        return {
            'show_delivery_route_e3_billing_fields': show_billing,
            'show_delivery_route_cost_fields': stage >= 3,
            'show_delivery_route_e1_minimal_form': stage == 1,
        }

    @api.depends_context(
        'from_route_lot_editor', 'delivery_route_stage', 'hide_delivery_e3_billing_fields',
        'route_editor_picking_id',
    )
    def _compute_show_delivery_route_e3_billing_fields(self):
        """Facturación visible solo desde E3 al editar serial en ruta de entrega."""
        flags = self._delivery_route_lot_visibility_flags(self.env)
        for lot in self:
            lot.show_delivery_route_e3_billing_fields = flags[
                'show_delivery_route_e3_billing_fields'
            ]

    @api.depends_context(
        'from_route_lot_editor', 'delivery_route_stage', 'route_editor_picking_id',
    )
    def _compute_show_delivery_route_cost_fields(self):
        """Costo / costo adicional ocultos en E1 y E2; visibles desde E3."""
        flags = self._delivery_route_lot_visibility_flags(self.env)
        for lot in self:
            lot.show_delivery_route_cost_fields = flags['show_delivery_route_cost_fields']

    @api.depends_context(
        'from_route_lot_editor', 'delivery_route_stage', 'route_editor_picking_id',
    )
    def _compute_show_delivery_route_e1_minimal_form(self):
        """E1: solo serial, placa inventario, producto, ubicación, foto y hoja de vida."""
        flags = self._delivery_route_lot_visibility_flags(self.env)
        for lot in self:
            lot.show_delivery_route_e1_minimal_form = flags[
                'show_delivery_route_e1_minimal_form'
            ]

    @api.depends_context(
        'from_route_lot_editor', 'delivery_route_stage', 'route_editor_picking_id',
    )
    def _compute_show_delivery_route_e2_plates_form(self):
        for lot in self:
            lot.show_delivery_route_e2_plates_form = False

    def web_read(self, specification):
        """Odoo 19: asegurar flags de etapa en el modal del serial (depends_context)."""
        spec = dict(specification or {})
        visibility_flag_names = (
            'show_delivery_route_e3_billing_fields',
            'show_delivery_route_cost_fields',
            'show_delivery_route_e1_minimal_form',
            'show_delivery_route_e2_plates_form',
        )
        # Campos usados en invisible= de la vista; solo asegurar que entren al spec.
        modifier_field_names = (
            'lot_valuated',
            'lot_classification',
            'show_subscription_service_fields',
        )
        ctx = self.env.context
        is_route_editor = bool(
            ctx.get('from_route_lot_editor') or ctx.get('route_editor_picking_id')
        )
        # Solo en lectura del formulario principal del serial (no sublecturas de componentes).
        is_main_lot_form = is_route_editor and (
            'inventory_plate' in spec
            or 'lot_supply_line_sin_costo_ids' in spec
            or 'lot_supply_line_con_costo_ids' in spec
        )
        if is_main_lot_form:
            for name in visibility_flag_names + modifier_field_names:
                spec.setdefault(name, {})
        result = super().web_read(spec)
        if not is_main_lot_form:
            return result
        flags = self._delivery_route_lot_visibility_flags(self.env)
        flags['show_delivery_route_e2_plates_form'] = False
        for vals in result:
            for name in visibility_flag_names:
                if name in spec:
                    vals[name] = flags.get(name, False)
        return result

    @api.depends(
        'subscription_service_product_id',
        'active_subscription_id',
        'reining_plazo',
        'entry_date',
        'product_id',
        'product_id.classification',
    )
    def _compute_invdash_delivery_billing_complete(self):
        for lot in self:
            lot.invdash_delivery_billing_complete = lot._invdash_delivery_billing_fields_complete()

    def _invdash_delivery_billing_fields_complete(self):
        self.ensure_one()
        return not bool(self.invdash_delivery_billing_missing_labels())

    def _invdash_delivery_billing_is_exempt(self):
        """True si el producto está clasificado y no requiere datos de facturación en E4.

        Cualquier clasificación exime salvo UPS, que sí debe pedir los datos.
        Los productos sin clasificación (equipos principales) no están exentos.
        """
        self.ensure_one()
        classification = self.product_id.classification if self.product_id else False
        return classification in DELIVERY_BILLING_EXEMPT_CLASSIFICATIONS

    def invdash_delivery_billing_missing_labels(self):
        self.ensure_one()
        if self._invdash_delivery_billing_is_exempt():
            return []
        missing = []
        for field_name, label in DELIVERY_BILLING_LOT_FIELDS:
            if field_name not in self._fields:
                continue
            if not self[field_name]:
                missing.append(label)
        return missing

    def invdash_e2_plates_missing_labels(self):
        """Placas faltantes en E2; misma exención por clasificación que facturación E4."""
        self.ensure_one()
        if self._invdash_delivery_billing_is_exempt():
            return []
        missing = []
        for field_name, label in DELIVERY_E2_LOT_FIELDS:
            if field_name not in self._fields:
                continue
            value = self[field_name]
            if value in (False, None, '') or (isinstance(value, str) and not value.strip()):
                missing.append(label)
        return missing

    def write(self, vals):
        res = super().write(vals)
        billing_fields = {f[0] for f in DELIVERY_BILLING_LOT_FIELDS}
        e2_fields = {f[0] for f in DELIVERY_E2_LOT_FIELDS}
        if billing_fields.intersection(vals.keys()) or e2_fields.intersection(vals.keys()):
            pickings = self.env['stock.picking'].search([
                ('move_line_ids.lot_id', 'in', self.ids),
                ('state', 'not in', ('done', 'cancel')),
                '|',
                ('origin', '=like', 'Ruta-%'),
                ('origin', '=like', 'Ruta:%'),
            ])
            if pickings:
                pickings.invalidate_recordset([
                    'invdash_delivery_billing_pending',
                    'invdash_delivery_billing_summary',
                ])
        return res
