# -*- coding: utf-8 -*-
from odoo import api, models

from .export_licenses_equipos_columns import (
    license_flags_for_template,
    equipment_flags_for_template,
    count_active_flags,
)


def _resolve_report_docids(env, docids, data):
    """Evita docs vacíos: al imprimir con data (asistente), res_ids a veces llega vacío y el PDF sale en blanco."""
    if docids not in (None, False):
        if isinstance(docids, int):
            return [docids]
        if isinstance(docids, (list, tuple)):
            out = [int(x) for x in docids if x is not None and x is not False]
            if out:
                return out
        if hasattr(docids, 'ids'):
            out = list(docids.ids)
            if out:
                return out
    data = data or {}
    if isinstance(data.get('doc_ids'), int):
        return [data['doc_ids']]
    if isinstance(data.get('doc_ids'), (list, tuple)) and data['doc_ids']:
        return [int(x) for x in data['doc_ids']]
    if isinstance(data.get('ids'), int):
        return [data['ids']]
    if isinstance(data.get('ids'), (list, tuple)) and data['ids']:
        return [int(x) for x in data['ids']]
    nested = data.get('context')
    if isinstance(nested, dict):
        if nested.get('active_ids'):
            return list(nested['active_ids'])
        if nested.get('active_id'):
            return [nested['active_id']]
    ctx = env.context
    if ctx.get('active_ids'):
        return list(ctx['active_ids'])
    if ctx.get('active_id'):
        return [ctx['active_id']]
    return []


class ReportExportLicensesEquiposPdf(models.AbstractModel):
    _name = 'report.subscription_nocount.report_export_licenses_equipos_pdf'
    _description = 'PDF export licencias y equipos (suscripción)'

    @api.model
    def _get_report_values(self, docids, data=None):
        ids = _resolve_report_docids(self.env, docids, data)
        docs = self.env['subscription.subscription'].browse(ids)
        lic_col = license_flags_for_template(data)
        eq_col = equipment_flags_for_template(data)
        return {
            'doc_ids': ids,
            'doc_model': 'subscription.subscription',
            'docs': docs,
            'company': self.env.company,
            'lic_col': lic_col,
            'eq_col': eq_col,
            'lic_col_count': count_active_flags(lic_col),
            'eq_col_count': count_active_flags(eq_col),
        }


class ReportExportMonthlyLicensesEquiposPdf(models.AbstractModel):
    _name = 'report.subscription_nocount.monthly_lic_eq_pdf'
    _description = 'PDF export licencias y equipos (facturable guardado)'

    @api.model
    def _get_report_values(self, docids, data=None):
        ids = _resolve_report_docids(self.env, docids, data)
        docs = self.env['subscription.monthly.billable'].browse(ids)
        lic_col = license_flags_for_template(data)
        eq_col = equipment_flags_for_template(data)
        return {
            'doc_ids': ids,
            'doc_model': 'subscription.monthly.billable',
            'docs': docs,
            'company': self.env.company,
            'lic_col': lic_col,
            'eq_col': eq_col,
            'lic_col_count': count_active_flags(lic_col),
            'eq_col_count': count_active_flags(eq_col),
        }
