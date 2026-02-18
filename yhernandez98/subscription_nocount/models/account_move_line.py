# -*- coding: utf-8 -*-
# La FK account_move_line_subscription_id_fkey apunta a sale_order (no a subscription.subscription).
# No escribir id de subscription.subscription en las líneas; solo sale.order es válido.
from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        """subscription_id en account.move.line referencia sale_order; no escribir id de subscription.subscription."""
        for vals in vals_list:
            move_id = vals.get('move_id')
            if move_id:
                move = self.env['account.move'].browse(move_id)
                if move.exists() and getattr(move, 'subscription_id', None):
                    sub = move.subscription_id
                    # Solo asignar si es sale.order; si es subscription.subscription dejar False
                    if sub._name == 'sale.order':
                        vals['subscription_id'] = sub.id
                    else:
                        vals['subscription_id'] = False
        return super().create(vals_list)
