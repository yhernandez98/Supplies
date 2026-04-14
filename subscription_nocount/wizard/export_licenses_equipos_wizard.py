# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubscriptionExportLicensesEquiposWizard(models.TransientModel):
    _name = 'subscription.export.licenses.equipos.wizard'
    _description = 'Exportar Licencias y Equipos'

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=False)
    billable_id = fields.Many2one('subscription.monthly.billable', string='Facturable guardado', required=False)

    # --- Columnas Licencias (por defecto todas) ---
    exp_lic_grouping = fields.Boolean(string='Lic. Agrupamiento', default=True)
    exp_lic_product = fields.Boolean(string='Lic. Producto', default=True)
    exp_lic_serial = fields.Boolean(string='Lic. Número de serie/lote', default=True)
    exp_lic_inventory_plate = fields.Boolean(string='Lic. Placa de Inventario', default=True)
    exp_lic_user = fields.Boolean(string='Lic. Usuario Asignado', default=True)
    exp_lic_license_service = fields.Boolean(string='Lic. Licencia/Servicio Asignado', default=True)
    exp_lic_cost = fields.Boolean(string='Lic. Costo', default=True)
    exp_lic_currency = fields.Boolean(string='Lic. Moneda', default=True)

    # --- Columnas Equipos (por defecto todas) ---
    exp_eq_grouping = fields.Boolean(string='Eq. Agrupamiento', default=True)
    exp_eq_product = fields.Boolean(string='Eq. Producto', default=True)
    exp_eq_inventory_plate = fields.Boolean(string='Eq. Placa de Inventario', default=True)
    exp_eq_serial = fields.Boolean(string='Eq. Serial/Lote', default=True)
    exp_eq_user = fields.Boolean(string='Eq. Usuario Asignado', default=True)
    exp_eq_cost_renting = fields.Boolean(string='Eq. Costo Renting', default=True)
    exp_eq_cost_additional = fields.Boolean(string='Eq. Costo Adicional', default=True)
    exp_eq_entry_date = fields.Boolean(string='Eq. Fecha Activación', default=True)
    exp_eq_exit_date = fields.Boolean(string='Eq. Fecha Finalización', default=True)
    exp_eq_reining_plazo = fields.Boolean(string='Eq. Plazo Renting', default=True)
    exp_eq_tiempo_sitio = fields.Boolean(string='Eq. Tiempo En Sitio', default=True)
    exp_eq_tiempo_restante = fields.Boolean(string='Eq. Tiempo Restante', default=True)
    exp_eq_days_service = fields.Boolean(string='Eq. Días En Servicio', default=True)
    exp_eq_cost_daily = fields.Boolean(string='Eq. Costo Diario', default=True)
    exp_eq_cost_to_date = fields.Boolean(string='Eq. Costo Días En Servicio', default=True)

    def _get_export_column_payload(self):
        self.ensure_one()
        return {
            'license': {
                'grouping': self.exp_lic_grouping,
                'product': self.exp_lic_product,
                'serial': self.exp_lic_serial,
                'inventory_plate': self.exp_lic_inventory_plate,
                'user': self.exp_lic_user,
                'license_service': self.exp_lic_license_service,
                'cost': self.exp_lic_cost,
                'currency': self.exp_lic_currency,
            },
            'equipment': {
                'grouping': self.exp_eq_grouping,
                'product': self.exp_eq_product,
                'inventory_plate': self.exp_eq_inventory_plate,
                'serial': self.exp_eq_serial,
                'user': self.exp_eq_user,
                'cost_renting': self.exp_eq_cost_renting,
                'cost_additional': self.exp_eq_cost_additional,
                'entry_date': self.exp_eq_entry_date,
                'exit_date': self.exp_eq_exit_date,
                'reining_plazo': self.exp_eq_reining_plazo,
                'tiempo_sitio': self.exp_eq_tiempo_sitio,
                'tiempo_restante': self.exp_eq_tiempo_restante,
                'days_service': self.exp_eq_days_service,
                'cost_daily': self.exp_eq_cost_daily,
                'cost_to_date': self.exp_eq_cost_to_date,
            },
        }

    def _validate_column_selection(self):
        payload = self._get_export_column_payload()
        lic_any = any(payload['license'].values())
        eq_any = any(payload['equipment'].values())
        if not lic_any and not eq_any:
            raise UserError(_('Seleccione al menos una columna en Licencias o en Equipos.'))
        return payload

    def action_export_excel(self):
        self.ensure_one()
        payload = self._validate_column_selection()
        data = {'export_columns': payload}
        if self.billable_id:
            data['doc_ids'] = list(self.billable_id.ids)
            return self.env.ref('subscription_nocount.action_report_export_monthly_licenses_equipos_xlsx').report_action(
                self.billable_id, data=data
            )
        if not self.subscription_id:
            raise UserError(_('Debe seleccionar una suscripción o un facturable guardado para exportar.'))
        data['doc_ids'] = list(self.subscription_id.ids)
        return self.env.ref('subscription_nocount.action_report_export_licenses_equipos_xlsx').report_action(
            self.subscription_id, data=data
        )

    def action_export_pdf(self):
        self.ensure_one()
        payload = self._validate_column_selection()
        data = {'export_columns': payload}
        if self.billable_id:
            data['doc_ids'] = list(self.billable_id.ids)
            return self.env.ref('subscription_nocount.action_report_export_monthly_licenses_equipos_pdf').report_action(
                self.billable_id, data=data
            )
        if not self.subscription_id:
            raise UserError(_('Debe seleccionar una suscripción o un facturable guardado para exportar.'))
        data['doc_ids'] = list(self.subscription_id.ids)
        return self.env.ref('subscription_nocount.action_report_export_licenses_equipos_pdf').report_action(
            self.subscription_id, data=data
        )

    def action_select_all_columns(self):
        self.ensure_one()
        for f in self._fields:
            if f.startswith('exp_lic_') or f.startswith('exp_eq_'):
                self[f] = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
