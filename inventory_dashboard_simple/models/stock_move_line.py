# -*- coding: utf-8 -*-
from odoo import models


class StockMoveLineDeliveryRoute(models.Model):
    _inherit = 'stock.move.line'

    def action_open_lot_wizard(self):
        action = super().action_open_lot_wizard()
        picking = self.picking_id or (self.move_id.picking_id if self.move_id else False)
        if picking and isinstance(action, dict):
            ctx = dict(action.get('context') or {})
            ctx.update(picking._delivery_route_lot_form_context())
            action['context'] = ctx
        return action
