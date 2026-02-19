# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class LicenseReportWizard(models.TransientModel):
    _name = 'license.report.wizard'
    _description = 'Asistente para Generar Reportes de Licencias'

    report_type = fields.Selection([
        ('by_partner', 'Por Cliente'),
        ('by_license', 'Por Tipo de Licencia'),
        ('by_cost', 'Costos por Período'),
        ('expiring', 'Vencidas y Próximas a Vencer'),
    ], string='Tipo de Reporte', required=True, default='by_partner')
    
    partner_ids = fields.Many2many(
        'res.partner',
        string='Clientes',
        domain=[('is_company', '=', True)],
        help='Deje vacío para incluir todos los clientes'
    )
    
    license_ids = fields.Many2many(
        'license.template',
        string='Tipos de Licencia',
        help='Deje vacío para incluir todos los tipos'
    )
    
    month = fields.Selection([
        ('01', 'Enero'),
        ('02', 'Febrero'),
        ('03', 'Marzo'),
        ('04', 'Abril'),
        ('05', 'Mayo'),
        ('06', 'Junio'),
        ('07', 'Julio'),
        ('08', 'Agosto'),
        ('09', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre'),
    ], string='Mes', default=lambda self: str(fields.Date.today().month).zfill(2))
    
    year = fields.Integer(
        string='Año',
        default=lambda self: fields.Date.today().year,
        required=True
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activa'),
        ('expired', 'Vencida'),
        ('cancelled', 'Cancelada'),
        ('all', 'Todos'),
    ], string='Estado', default='active', required=True)
    
    include_equipment = fields.Boolean(
        string='Incluir Detalle de Equipos',
        default=True,
        help='Incluir información detallada de equipos asignados'
    )
    
    include_users = fields.Boolean(
        string='Incluir Detalle de Usuarios',
        default=True,
        help='Incluir información detallada de usuarios asignados'
    )
    
    assignments_ids = fields.Many2many(
        'license.assignment',
        string='Asignaciones',
        readonly=True,
        help='Asignaciones seleccionadas para el reporte'
    )

    def action_generate_report(self):
        """Genera el reporte según el tipo seleccionado"""
        self.ensure_one()
        
        # Construir dominio base
        domain = []
        
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        
        if self.license_ids:
            domain.append(('license_id', 'in', self.license_ids.ids))
        
        if self.state != 'all':
            domain.append(('state', '=', self.state))
        
        # Filtrar por mes si se indicó (asignación activa que solapa con ese mes)
        if self.month and self.year and self.report_type != 'expiring':
            start_date = datetime(int(self.year), int(self.month), 1).date()
            end_date = (start_date + relativedelta(months=1) - timedelta(days=1))
            if self.report_type in ['by_cost', 'by_partner', 'by_license']:
                domain.append(('state', '=', 'active'))
                domain.append(('start_date', '<=', end_date))
                domain.append(('end_date', '>=', start_date))
        
        # Obtener asignaciones
        assignments = self.env['license.assignment'].search(domain, order='partner_id, license_id')
        
        if self.report_type == 'expiring':
            today = fields.Date.today()
            next_month = today + relativedelta(months=1)
            assignments = assignments.filtered(
                lambda a: a.end_date and (
                    a.end_date <= today or (a.end_date > today and a.end_date <= next_month)
                ) and a.state == 'active'
            )
        
        if not assignments:
            raise UserError(_('No se encontraron asignaciones con los criterios seleccionados.'))
        
        # Ordenar según el tipo de reporte y guardar en el wizard (el orden se preserva en assignments_ids)
        if self.report_type == 'by_partner':
            sorted_assignments = assignments.sorted(key=lambda a: (a.partner_id.name or '', a.license_id.name or ''))
        elif self.report_type == 'by_license':
            sorted_assignments = assignments.sorted(key=lambda a: (a.license_id.name or '', a.partner_id.name or ''))
        else:
            sorted_assignments = assignments
        self.write({'assignments_ids': [(6, 0, sorted_assignments.ids)]})
        
        # Retornar acción de reporte según el tipo
        if self.report_type == 'by_partner':
            return self._get_partner_report_action(sorted_assignments)
        elif self.report_type == 'by_license':
            return self._get_license_report_action(sorted_assignments)
        elif self.report_type == 'by_cost':
            return self._get_cost_report_action()
        elif self.report_type == 'expiring':
            return self._get_expiring_report_action()
    
    def _get_partner_report_action(self, sorted_assignments):
        """Retorna la acción para el reporte por cliente (orden ya guardado en assignments_ids)."""
        return self._report_action('subscription_licenses.report_license_by_partner_template')

    def _get_license_report_action(self, sorted_assignments):
        """Retorna la acción para el reporte por tipo de licencia."""
        return self._report_action('subscription_licenses.report_license_by_type_template')

    def _get_cost_report_action(self):
        """Retorna la acción para el reporte de costos."""
        return self._report_action('subscription_licenses.report_license_costs_template')

    def _get_expiring_report_action(self):
        """Retorna la acción para el reporte de vencidas."""
        return self._report_action('subscription_licenses.report_license_expiring_template')

    def _report_action(self, report_name):
        """Acción común para abrir el PDF del reporte."""
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'model': 'license.report.wizard',
            'res_id': self.id,
        }

