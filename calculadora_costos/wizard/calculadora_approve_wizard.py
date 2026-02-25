# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class CalculadoraApproveWizard(models.TransientModel):
    _name = 'calculadora.approve.wizard'
    _description = 'Aprobar cotización Renting y cargar a lista de precios'

    calculadora_id = fields.Many2one(
        'calculadora.costos',
        string='Cotización',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='calculadora_id.partner_id',
        string='Cliente',
        readonly=True,
    )
    approved_plazo_meses = fields.Selection([
        ('12', '12 meses'),
        ('24', '24 meses'),
        ('36', '36 meses'),
        ('48', '48 meses'),
        ('60', '60 meses'),
    ], string='Plazo (meses)', required=True,
       help='Plazo con el que el cliente aprueba la cotización.')
    approved_escenario_key = fields.Selection([
        ('escenario_1', 'Escenario 1: Con Seguro y Servicios Técnicos'),
        ('escenario_2', 'Escenario 2: Sin Seguro pero con Servicios Técnicos'),
        ('escenario_3', 'Escenario 3: Con Seguro pero sin Servicios Técnicos'),
        ('escenario_4', 'Escenario 4: Sin Seguro ni Servicios Técnicos'),
    ], string='Escenario', required=True,
       help='Escenario elegido por el cliente (seguro y/o servicios).')

    def action_approve_and_load(self):
        self.ensure_one()
        if not self.calculadora_id or self.calculadora_id.tipo_operacion != 'renting':
            raise UserError('Solo se puede aprobar una cotización de tipo Renting.')
        plazo = int(self.approved_plazo_meses)
        self.calculadora_id.action_approve_and_load_pricelist(
            plazo_meses=plazo,
            escenario_key=self.approved_escenario_key,
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calculadora.costos',
            'res_id': self.calculadora_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
