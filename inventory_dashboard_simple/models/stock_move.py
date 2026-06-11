# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models


def _clean_product_label(name):
    if not name:
        return ''
    return re.sub(r'^\s*\[[^\]]+\]\s*', '', name).strip()


class StockMoveDeliveryRoute(models.Model):
    _inherit = 'stock.move'

    invdash_return_e4_anchor_only = fields.Boolean(
        string='Ancla E4 (sin mover stock)',
        default=False,
        copy=False,
        help='Movimiento principal de referencia cuando los asociados van solos a otro destino.',
    )
    invdash_return_e4_principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial principal E4',
        copy=False,
        help='Serial del equipo principal para mostrar la fila en PRODUCTO PRINCIPAL.',
    )

    def _action_done(self, cancel_backorder=False):
        """Cierre administrativo del E4 de ruta tras clasificación (sin mover stock otra vez)."""
        if self.env.context.get('invdash_return_e4_admin_close'):
            moves = self.filtered(lambda m: m.state not in ('done', 'cancel'))
            if moves:
                moves.write({'state': 'done'})
            return True
        return super()._action_done(cancel_backorder=cancel_backorder)

    @api.depends(
        'move_line_ids',
        'move_line_ids.lot_id',
        'move_line_ids.lot_id.lot_supply_line_ids',
        'move_line_ids.lot_id.lot_supply_line_ids.related_lot_id',
        'move_line_ids.lot_id.lot_supply_line_ids.item_type',
        'move_line_ids.lot_id.lot_supply_line_ids.related_lot_id.name',
        'supply_kind',
        'internal_child_move_ids',
        'internal_child_move_ids.move_line_ids',
        'internal_child_move_ids.move_line_ids.lot_id',
        'internal_child_move_ids.supply_kind',
        'picking_id.invdash_is_return_e4_classification',
        'invdash_return_e4_principal_lot_id',
    )
    def _compute_associated_elements(self):
        super()._compute_associated_elements()
        for move in self.filtered(
            lambda m: m.supply_kind == 'parent'
            and m.picking_id
            and m.picking_id.invdash_is_return_e4_classification
        ):
            if move.associated_components or move.associated_peripherals or move.associated_complements:
                continue
            move._return_e4_fill_associated_from_child_moves()

    def _return_e4_fill_associated_from_child_moves(self):
        """Muestra asociados en columnas del padre aunque ya no estén en lot_supply_line."""
        self.ensure_one()
        components = []
        peripherals = []
        complements = []
        for child in self.internal_child_move_ids:
            for ml in child.move_line_ids.filtered('lot_id'):
                serial_name = ml.lot_id.name or ''
                if not serial_name:
                    continue
                product_name = _clean_product_label(
                    ml.product_id.name or ml.product_id.display_name or '',
                )
                display_text = (
                    '%s (%s)' % (product_name, serial_name)
                    if product_name else serial_name
                )
                kind = child.supply_kind or 'component'
                if kind == 'component':
                    components.append(display_text)
                elif kind in ('peripheral', 'monitor', 'ups'):
                    peripherals.append(display_text)
                elif kind == 'complement':
                    complements.append(display_text)
                else:
                    peripherals.append(display_text)
        self.associated_components = '\n'.join(components) if components else ''
        self.associated_peripherals = '\n'.join(peripherals) if peripherals else ''
        self.associated_complements = '\n'.join(complements) if complements else ''

    def action_open_lot_wizard(self):
        action = super().action_open_lot_wizard()
        picking = self.picking_id
        if picking and isinstance(action, dict):
            ctx = dict(action.get('context') or {})
            ctx.update(picking._delivery_route_lot_form_context())
            action['context'] = ctx
        return action
