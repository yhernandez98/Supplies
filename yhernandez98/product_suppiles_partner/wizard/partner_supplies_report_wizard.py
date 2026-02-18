# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PartnerSuppliesReportWizard(models.TransientModel):
    _name = 'partner.supplies.report.wizard'
    _description = 'Asistente de Reporte de Productos Serializados por Contacto'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto/Empresa',
        required=True,
        help='Seleccione el contacto o empresa para generar el reporte'
    )
    
    report_type = fields.Selection([
        ('view', 'Ver en pantalla'),
        ('xlsx', 'Descargar Excel'),
        ('pdf', 'Descargar PDF'),
    ], string='Tipo de Reporte', required=True, default='view',
       help='Seleccione el formato del reporte a generar')
    
    include_components = fields.Boolean(
        string='Incluir Componentes',
        default=True,
        help='Incluir componentes, periféricos y complementos en el reporte'
    )
    
    observation = fields.Text(
        string='Observaciones',
        help='Observaciones adicionales para incluir en el reporte'
    )

    def _ref(self, xmlid):
        """Obtiene referencia a un XMLID de forma segura"""
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        if not rec:
            raise UserError(_("No se encontró el XMLID: %s") % xmlid)
        return rec

    def action_generate_report(self):
        """Genera el reporte según el tipo seleccionado"""
        self.ensure_one()
        
        # Validar que el contacto tenga seriales asignados
        if not self.partner_id.main_lot_ids:
            raise UserError(_('El contacto seleccionado no tiene productos/seriales asignados.'))
        
        data = {
            'partner_id': self.partner_id.id,
            'observation': self.observation or '',
            'include_components': self.include_components,
        }
        
        report_type = (self.report_type or '').lower()
        
        if report_type == 'pdf':
            return self.env.ref(
                'product_suppiles_partner.action_partner_supplies_report_pdf'
            ).report_action(self)
        
        elif report_type == 'xlsx':
            return self._ref(
                'product_suppiles_partner.action_partner_supplies_report_xlsx'
            ).report_action(self, data=data)
        
        else:  # view
            domain = [('related_partner_id', '=', self.partner_id.id)]
            lots = self.partner_id.main_lot_ids if not self.include_components else self.partner_id.all_lot_ids
            domain = [('id', 'in', lots.ids)]
            
            return {
                'name': _('Productos Serializados de %s') % self.partner_id.name,
                'type': 'ir.actions.act_window',
                'res_model': 'stock.lot',
                'view_mode': 'list,form',
                'domain': domain,
                'context': {
                    'default_related_partner_id': self.partner_id.id,
                    'search_default_filter_today': 1
                },
            }

