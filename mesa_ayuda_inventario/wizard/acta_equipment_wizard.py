# -*- coding: utf-8 -*-

import json

from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import mail as mail_tools

from .acta_html_blocks import mesa_acta_equipment_block_html


def _mesa_acta_wizard_text(value):
    """Texto seguro para campos Char / columnas que puedan venir como dict/list."""
    if value is None or value is False:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


class MesaAyudaActaEquipmentWizard(models.TransientModel):
    _name = 'mesa.ayuda.acta.equipment.wizard'
    _description = 'Elegir equipos principales para el acta de visita'

    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    filter_equipment = fields.Char(
        string='Buscar',
        help='Filtra la lista por producto, referencia interna, número de serie o placa de inventario.',
    )
    # Lotes candidatos (solo lectura en UI); selected_lot_ids se limita a estos.
    candidate_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_acta_eq_wiz_cand_lot_rel',
        'wizard_id',
        'lot_id',
        string='Equipos disponibles',
    )
    # many2many_checkboxes: la selección se integra bien con el guardado del formulario
    # (las filas editables + boolean «Incluir» no siempre llegaban al servidor al pulsar el botón).
    selected_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_acta_eq_wiz_sel_lot_rel',
        'wizard_id',
        'lot_id',
        string='Equipos para el acta',
        domain="[('id', 'in', candidate_lot_ids)]",
    )
    has_acta_equipment_lines = fields.Boolean(
        compute='_compute_has_acta_equipment_lines',
    )

    @api.depends('selected_lot_ids')
    def _compute_has_acta_equipment_lines(self):
        for wiz in self:
            wiz.has_acta_equipment_lines = bool(wiz.selected_lot_ids)

    def _mesa_acta_all_candidate_lots(self):
        self.ensure_one()
        if not self.ticket_id:
            return self.env['stock.lot']
        return self.ticket_id._mesa_candidate_main_lots_for_acta()

    def _mesa_acta_filtered_lots(self):
        self.ensure_one()
        lots = self._mesa_acta_all_candidate_lots()
        needle = (self.filter_equipment or '').strip().lower()
        if not needle:
            return lots

        def match(lot):
            prod = lot.product_id
            parts = [
                prod.name or '',
                prod.default_code or '',
                prod.display_name or '',
                lot.name or '',
                (lot.inventory_plate or ''),
            ]
            return needle in ' '.join(parts).lower()

        return lots.filtered(match)

    @api.onchange('filter_equipment')
    def _onchange_filter_equipment(self):
        if not self.ticket_id:
            return
        lots = self._mesa_acta_filtered_lots()
        self.candidate_lot_ids = [(6, 0, lots.ids)]
        keep = self.selected_lot_ids.filtered(lambda l: l.id in lots.ids)
        if keep.ids != self.selected_lot_ids.ids:
            self.selected_lot_ids = [(6, 0, keep.ids)]

    def write(self, vals):
        res = super().write(vals)
        if 'filter_equipment' in vals and any(self.mapped('ticket_id')):
            for wiz in self.filtered('ticket_id'):
                lots = wiz._mesa_acta_filtered_lots()
                wiz.candidate_lot_ids = [(6, 0, lots.ids)]
                keep = wiz.selected_lot_ids.filtered(lambda l: l.id in lots.ids)
                if keep.ids != wiz.selected_lot_ids.ids:
                    wiz.selected_lot_ids = [(6, 0, keep.ids)]
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tid = self.env.context.get('default_ticket_id')
        if not tid:
            return res
        ticket = self.env['helpdesk.ticket'].browse(tid).exists()
        if not ticket:
            return res
        lots = ticket._mesa_candidate_main_lots_for_acta()
        if not lots:
            raise UserError(
                _(
                    'No se encontraron productos principales para el cliente de este ticket '
                    '(ni en la orden de visita ni en inventario / ubicación de cliente). '
                    'Revise que el cliente tenga lotes marcados como principales o stock en su ubicación.'
                )
            )
        if 'ticket_id' in fields_list:
            res['ticket_id'] = ticket.id
        if 'candidate_lot_ids' in fields_list:
            res['candidate_lot_ids'] = [(6, 0, lots.ids)]
        if 'selected_lot_ids' in fields_list:
            res['selected_lot_ids'] = [(6, 0, [])]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        ctx_tid = self.env.context.get('default_ticket_id')
        clean = []
        for vals in vals_list:
            v = dict(vals or {})
            if ctx_tid and not v.get('ticket_id'):
                v['ticket_id'] = ctx_tid
            clean.append(v)
        records = super().create(clean)
        for wiz in records:
            if wiz.ticket_id and not wiz.candidate_lot_ids:
                lots = wiz.ticket_id._mesa_candidate_main_lots_for_acta()
                if lots:
                    wiz.candidate_lot_ids = lots
        return records

    def action_confirm_insert(self):
        self.ensure_one()
        order = self.ticket_id.maintenance_order_id
        if not order:
            raise UserError(_('El ticket no tiene orden de visita vinculada.'))
        lots = self.selected_lot_ids.filtered(lambda l: l.id in self.candidate_lot_ids.ids)
        if not lots:
            raise UserError(_('Marque al menos un equipo para insertar en el acta.'))
        th_serie = _('Serie')
        th_placa = _('Placa')
        th_prod = _('Producto')
        th_realizado = _('Realizado')
        blocks = []
        for lot in lots.sorted(lambda l: ((l.product_id.name or ''), (l.name or ''))):
            serial = escape(lot.name or '')
            plate = escape(_mesa_acta_wizard_text(lot.inventory_plate) or _('Sin placa'))
            prod = escape(lot.product_id.display_name if lot.product_id else _('N/A'))
            blocks.append(
                mesa_acta_equipment_block_html(
                    lot.id, th_serie, th_placa, th_prod, serial, plate, prod, th_realizado,
                    lbl_equipment_change=_('Cambio de Equipo'),
                    lbl_component_change=_('Cambio de Componente'),
                    lbl_maintenance_repair=_('Mantenimiento/Reparación'),
                )
            )
        blocks.append('<p></p>')
        table = ''.join(blocks)
        # ``visit_documentation_html`` puede ser ``markupsafe.Markup``; ``Markup + str`` escapa el fragmento nuevo.
        cur = str(order.visit_documentation_html or '')
        if mail_tools.is_html_empty(order.visit_documentation_html):
            order.write({'visit_documentation_html': table})
        else:
            order.write({'visit_documentation_html': cur + table})
        # Registrar lotes para generar tickets hijos al resolver la visita (solo ese flujo).
        if lots:
            self.ticket_id.write({'mesa_acta_selected_lot_ids': [(4, lid) for lid in lots.ids]})
        return {'type': 'ir.actions.act_window_close'}
