# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LeasingContractWizard(models.TransientModel):
    """Wizard para crear contratos de leasing desde órdenes de compra."""
    _name = 'leasing.contract.wizard'
    _description = 'Wizard para Crear Contrato de Leasing'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra',
        required=True,
        readonly=True,
    )
    brand_ids = fields.Many2many(
        'leasing.brand',
        string='Marcas',
        required=True,
        help='Marcas incluidas en el contrato (ej: HP, Dell, etc.). Puede seleccionar múltiples marcas.'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        domain="[('is_company', '=', True)]",
        help='Cliente que firma el contrato (la gran empresa)'
    )
    start_date = fields.Date(
        string='Fecha Inicio',
        required=True,
        default=fields.Date.today
    )
    end_date = fields.Date(
        string='Fecha Fin',
        help='Fecha de finalización del contrato (opcional)'
    )
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el contrato'
    )
    template_id = fields.Many2one(
        'leasing.contract.template',
        string='Plantilla',
        domain="[('active', '=', True)]",
        help='Plantilla que se usará para generar el contrato (opcional)'
    )

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto desde la orden de compra."""
        res = super().default_get(fields_list)
        
        purchase_order_id = self.env.context.get('default_purchase_order_id') or \
                          self.env.context.get('active_id')
        
        if purchase_order_id:
            po = self.env['purchase.order'].browse(purchase_order_id)
            if po.exists():
                res['purchase_order_id'] = po.id
                
                # Prellenar marca si hay una seleccionada
                if 'brand_ids' in fields_list and po.leasing_brand_id:
                    res['brand_ids'] = [(6, 0, [po.leasing_brand_id.id])]
                
                # Prellenar cliente desde órdenes de venta relacionadas
                if 'partner_id' in fields_list and po.partner_customer_ids:
                    if len(po.partner_customer_ids) == 1:
                        res['partner_id'] = po.partner_customer_ids[0].id
                    elif len(po.partner_customer_ids) > 1:
                        # Si hay múltiples clientes, usar el primero
                        res['partner_id'] = po.partner_customer_ids[0].id
        
        return res

    def action_create_contract(self):
        """Crear el contrato de leasing y asociarlo a la orden de compra."""
        self.ensure_one()
        
        if not self.brand_ids:
            raise UserError(_('Debe seleccionar al menos una marca para el contrato.'))
        
        # Crear el contrato
        contract_vals = {
            'brand_ids': [(6, 0, self.brand_ids.ids)],
            'partner_id': self.partner_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date if self.end_date else False,
            'notes': self.notes if self.notes else False,
            'template_id': self.template_id.id if self.template_id else False,
            'state': 'draft',
        }
        
        contract = self.env['leasing.contract'].create(contract_vals)
        
        # Asociar el contrato a la orden de compra
        if self.purchase_order_id:
            self.purchase_order_id.write({
                'leasing_contract_id': contract.id,
                'is_leasing': True,
            })
        
        # Retornar acción para ver el contrato creado
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrato de Leasing Creado'),
            'res_model': 'leasing.contract',
            'res_id': contract.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

