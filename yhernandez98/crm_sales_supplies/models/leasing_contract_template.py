# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LeasingContractTemplate(models.Model):
    """Plantillas para contratos de leasing que se pueden usar al crear contratos."""
    _name = 'leasing.contract.template'
    _description = 'Plantilla de Contrato de Leasing'
    _inherit = ['mail.thread']
    _order = 'name asc'

    name = fields.Char(
        string='Nombre de la Plantilla',
        required=True,
        tracking=True,
        help='Nombre descriptivo de la plantilla (ej: "Contrato HP Estándar", "Contrato Dell Básico")'
    )
    active = fields.Boolean(
        string='Activa',
        default=True,
        tracking=True
    )
    description = fields.Text(
        string='Descripción',
        help='Descripción de cuándo y cómo usar esta plantilla'
    )
    
    # Contenido del contrato
    contract_content = fields.Html(
        string='Contenido del Contrato',
        required=True,
        help='Contenido HTML del contrato. Puede usar variables como:\n'
             '%(contract_name)s - Número del contrato\n'
             '%(partner_name)s - Nombre del cliente\n'
             '%(brand_names)s - Nombres de las marcas\n'
             '%(start_date)s - Fecha de inicio\n'
             '%(end_date)s - Fecha de fin\n'
             '%(provider_names)s - Nombres de proveedores\n'
             '%(notes)s - Notas del contrato'
    )
    
    # Adjunto PDF de la plantilla (si se carga un PDF original)
    template_pdf = fields.Binary(
        string='PDF de Plantilla',
        help='PDF original de la plantilla (opcional). Se puede adjuntar para referencia.'
    )
    template_pdf_filename = fields.Char(
        string='Nombre del Archivo PDF'
    )
    
    # Estadísticas
    usage_count = fields.Integer(
        string='Veces Usada',
        compute='_compute_usage_count',
        store=False,
        help='Número de contratos creados usando esta plantilla'
    )
    
    def _compute_usage_count(self):
        """Calcular cuántas veces se ha usado esta plantilla."""
        for template in self:
            template.usage_count = self.env['leasing.contract'].search_count([
                ('template_id', '=', template.id)
            ])

    def action_view_contracts_using_template(self):
        """Ver todos los contratos que usaron esta plantilla."""
        self.ensure_one()
        contracts = self.env['leasing.contract'].search([
            ('template_id', '=', self.id)
        ])
        return {
            'name': _('Contratos usando esta Plantilla'),
            'type': 'ir.actions.act_window',
            'res_model': 'leasing.contract',
            'view_mode': 'list,form',
            'domain': [('id', 'in', contracts.ids)],
            'context': {'search_default_template_id': self.id},
        }

