# -*- coding: utf-8 -*-
from odoo import _, fields, models


class PurchaseAlert(models.Model):
    _inherit = 'purchase.alert'

    integration_case_ids = fields.One2many(
        'commercial.integration.case',
        'purchase_alert_id',
        string='Casos integración',
        readonly=True,
    )
    integration_case_count = fields.Integer(
        string='Casos integración',
        compute='_compute_integration_case_count',
    )

    def _compute_integration_case_count(self):
        for alert in self:
            alert.integration_case_count = len(alert.integration_case_ids)

    def action_open_or_create_integration_case(self):
        self.ensure_one()
        Case = self.env['commercial.integration.case']
        case = Case.get_or_create_for_alert(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Caso integración'),
            'res_model': 'commercial.integration.case',
            'res_id': case.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_notify_creator_quotations_ready(self):
        """Mantiene el comportamiento original y prepara la propuesta sin cotización ganadora."""
        res = super().action_notify_creator_quotations_ready()
        Case = self.env['commercial.integration.case']
        for alert in self.filtered(lambda a: a.purchase_order_ids):
            case = Case.get_or_create_for_alert(alert)
            if not case.calculadora_id:
                try:
                    case._sync_calculadora_from_alert_quotes(alert)
                except Exception:
                    # El flujo de "cotizaciones listas" no debe romperse por falta de datos en alguna cotización.
                    continue
            if case.state in ('draft', 'awaiting_quotes'):
                case.state = 'calculator_ready'
        return res
