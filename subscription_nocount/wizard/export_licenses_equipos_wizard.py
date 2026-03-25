# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubscriptionExportLicensesEquiposWizard(models.TransientModel):
    _name = 'subscription.export.licenses.equipos.wizard'
    _description = 'Exportar Licencias y Equipos'

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=False)
    billable_id = fields.Many2one('subscription.monthly.billable', string='Facturable guardado', required=False)

    @api.model
    def _get_active_subscription(self, subscription_id):
        return self.env['subscription.subscription'].browse(subscription_id)

    def action_export_excel(self):
        self.ensure_one()
        if self.billable_id:
            return self.env.ref('subscription_nocount.action_report_export_monthly_licenses_equipos_xlsx').report_action(
                self.billable_id
            )
        if not self.subscription_id:
            raise UserError(_('Debe seleccionar una suscripción o un facturable guardado para exportar.'))
        return self.env.ref('subscription_nocount.action_report_export_licenses_equipos_xlsx').report_action(self.subscription_id)

    def action_export_pdf(self):
        self.ensure_one()
        if self.billable_id:
            return self.env.ref('subscription_nocount.action_report_export_monthly_licenses_equipos_pdf').report_action(
                self.billable_id
            )
        if not self.subscription_id:
            raise UserError(_('Debe seleccionar una suscripción o un facturable guardado para exportar.'))
        return self.env.ref('subscription_nocount.action_report_export_licenses_equipos_pdf').report_action(self.subscription_id)

