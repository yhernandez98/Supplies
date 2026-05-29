# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DeliveryRouteValidationWizard(models.TransientModel):
    _name = 'delivery.route.validation.wizard'
    _description = 'Validación ruta de entrega — campos pendientes'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán',
        required=True,
        ondelete='cascade',
    )
    validation_type = fields.Selection(
        selection=[
            ('e2_plates', 'E2 — Placas'),
            ('e4_billing', 'E4 — Facturación'),
            ('e4_e3_pending', 'E4 — Falta validar E3'),
        ],
        string='Tipo',
        required=True,
    )
    title = fields.Char(compute='_compute_title')
    subtitle = fields.Char(compute='_compute_title')
    line_ids = fields.One2many(
        'delivery.route.validation.wizard.line',
        'wizard_id',
        string='Pendientes',
    )

    @api.depends('validation_type')
    def _compute_title(self):
        for wiz in self:
            if wiz.validation_type == 'e2_plates':
                wiz.title = _('No puede validar la etapa E2')
                wiz.subtitle = _(
                    'Complete Placa de Inventario y Placa de Seguridad en cada serial antes de pasar a E3.'
                )
            elif wiz.validation_type == 'e4_billing':
                wiz.title = _('No puede validar la etapa E4')
                wiz.subtitle = _(
                    'Complete Servicio, Suscripción, Plazo Renting y Fecha Activación Renting en cada serial.'
                )
            else:
                wiz.title = _('No puede validar la etapa E4')
                wiz.subtitle = _(
                    'Debe validar antes el traslado Salida → Transporte (etapa E3).'
                )

    def action_open_incomplete_lots(self):
        self.ensure_one()
        picking = self.picking_id
        if self.validation_type == 'e2_plates':
            lots = picking._delivery_e2_plates_incomplete_lots()
        elif self.validation_type == 'e4_billing':
            lots = picking._delivery_billing_incomplete_lots()
        else:
            e3 = picking._route_picking_for_stage(3)
            if e3:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'res_id': e3.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            return {'type': 'ir.actions.act_window_close'}
        if not lots:
            return {'type': 'ir.actions.act_window_close'}
        lot = lots[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Completar serial — %s') % (lot.name or lot.display_name),
            'res_model': 'stock.lot',
            'res_id': lot.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(
                picking._delivery_route_lot_form_context(),
                form_view_initial_mode='edit',
            ),
        }

    def action_open_all_lots(self):
        self.ensure_one()
        if self.validation_type == 'e4_e3_pending':
            return self.action_open_incomplete_lots()
        picking = self.picking_id
        if self.validation_type == 'e2_plates':
            lots = picking._delivery_e2_plates_incomplete_lots()
        else:
            return picking.action_open_delivery_billing_lots()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seriales pendientes — %s') % (picking.display_name or picking.name),
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', lots.ids)],
            'context': dict(
                picking._delivery_route_lot_form_context(),
                form_view_initial_mode='edit',
            ),
        }


class DeliveryRouteValidationWizardLine(models.TransientModel):
    _name = 'delivery.route.validation.wizard.line'
    _description = 'Línea validación ruta entrega'
    _order = 'id'

    wizard_id = fields.Many2one(
        'delivery.route.validation.wizard',
        required=True,
        ondelete='cascade',
    )
    detail = fields.Char(string='Detalle', required=True)
