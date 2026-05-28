# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    commercial_integration_case_ids = fields.One2many(
        'commercial.integration.case',
        'winning_purchase_order_id',
        string='Casos como ganadora',
        readonly=True,
    )

    def action_mark_as_winning_quote_integration(self):
        """Marca esta cotización como ganadora y sincroniza la calculadora (módulo puente)."""
        self.ensure_one()
        alert = self.env['purchase.alert'].search([('purchase_order_ids', 'in', self.id)], limit=1)
        if not alert:
            raise UserError(_('Esta orden no está vinculada a una alerta por cotización.'))
        Case = self.env['commercial.integration.case']
        existing = Case.search([('winning_purchase_order_id', '=', self.id)], limit=1)
        if existing:
            existing.action_set_winning_purchase_order(self)
            existing._continue_flow_if_any_approval()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'commercial.integration.case',
                'res_id': existing.id,
                'view_mode': 'form',
                'target': 'current',
            }
        case = Case.get_or_create_for_alert(alert)
        case.action_set_winning_purchase_order(self)
        case._continue_flow_if_any_approval()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commercial.integration.case',
            'res_id': case.id,
            'view_mode': 'form',
            'target': 'current',
        }
