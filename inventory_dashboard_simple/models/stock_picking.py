# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    component_lab_temp_out = fields.Boolean(
        string='Traslado lab. (pendiente validar)',
        default=False,
        copy=False,
        help='Traslado Existencias → Supp/Laboratorio creado desde el wizard; queda abierto hasta validar o cancelar.',
    )
    component_lab_loan_active = fields.Boolean(
        string='Préstamo lab. activo',
        default=False,
        copy=False,
        help='Salida a laboratorio ya validada; sigue activo hasta validar la devolución (traslado inverso) enlazada.',
    )
    component_lab_pending_responsible_approval = fields.Boolean(
        string='Devolución pendiente aprobación (responsable lab.)',
        default=False,
        copy=False,
        help='La devolución ya está validada en inventario; el responsable de laboratorio debe aprobar el cierre del préstamo.',
    )
    component_lab_loan_completed = fields.Boolean(
        string='Préstamo lab. completado',
        default=False,
        copy=False,
        help='Tras la aprobación del responsable; el préstamo figura como «Completado» en el seguimiento.',
    )
    component_lab_tracking_phase = fields.Char(
        string='Fase préstamo lab.',
        compute='_compute_component_lab_tracking_phase',
    )
    lab_responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable (lab.)',
        domain=[('share', '=', False)],
        copy=False,
    )
    lab_technician_user_id = fields.Many2one(
        'res.users',
        string='Técnico asignado (lab.)',
        domain=[('share', '=', False)],
        copy=False,
    )
    component_lab_return_picking_id = fields.Many2one(
        'stock.picking',
        string='Devolución enlazada',
        copy=False,
        readonly=True,
        help='Último albarán de devolución (Lab. → Existencias) asociado desde el wizard.',
    )
    component_lab_source_loan_picking_id = fields.Many2one(
        'stock.picking',
        string='Préstamo origen (salida lab.)',
        copy=False,
        help='Albarán de salida a laboratorio al que corresponde esta devolución.',
    )
    component_lab_pool_intake = fields.Boolean(
        string='Ingreso pool laboratorio (nuevo flujo)',
        default=False,
        copy=False,
        help='Traslado Existencias → Lab. que genera líneas en «Asignaciones laboratorio» al validarse.',
    )
    component_lab_pool_exit = fields.Boolean(
        string='Salida pool lab. a Existencias',
        default=False,
        copy=False,
    )

    def _component_lab_create_pool_assignments(self):
        """Crea component.lab.assignment por serial al validar ingreso a laboratorio (pool)."""
        self.ensure_one()
        Assignment = self.env['component.lab.assignment']
        if not self.lab_responsible_user_id:
            raise UserError(_('No se puede crear el pool de laboratorio sin responsable asignado.'))
        seen_lots = set()
        for sml in self.move_line_ids:
            if not sml.lot_id or not sml.product_id:
                continue
            qty = sml.quantity
            rounding = sml.product_uom_id.rounding
            if float_is_zero(qty, precision_rounding=rounding):
                continue
            if sml.lot_id.id in seen_lots:
                continue
            seen_lots.add(sml.lot_id.id)
            if Assignment.search_count([
                ('intake_picking_id', '=', self.id),
                ('lot_id', '=', sml.lot_id.id),
            ]):
                continue
            Assignment.create({
                'intake_picking_id': self.id,
                'lot_id': sml.lot_id.id,
                'product_id': sml.product_id.id,
                'responsible_user_id': self.lab_responsible_user_id.id,
                'state': 'in_lab_pool',
            })

    @api.depends(
        'component_lab_temp_out',
        'component_lab_loan_active',
        'component_lab_loan_completed',
        'component_lab_pending_responsible_approval',
        'state',
    )
    def _compute_component_lab_tracking_phase(self):
        for p in self:
            if p.component_lab_loan_completed and p.state == 'done':
                p.component_lab_tracking_phase = _('Completado (devuelto)')
            elif p.component_lab_pending_responsible_approval and p.state == 'done':
                p.component_lab_tracking_phase = _('Devuelto (pendiente aprobación responsable)')
            elif p.state == 'done' and p.component_lab_loan_active:
                p.component_lab_tracking_phase = _('Préstamo activo (falta devolución)')
            elif p.state not in ('done', 'cancel') and p.component_lab_temp_out:
                p.component_lab_tracking_phase = _('Pendiente validar salida')
            else:
                p.component_lab_tracking_phase = ''

    def action_lab_loan_responsible_approve(self):
        """Solo el responsable (lab.) del préstamo puede pasar la fase a completado."""
        for picking in self:
            if not picking.component_lab_pending_responsible_approval:
                raise UserError(_('Este albarán no está pendiente de aprobación del responsable de laboratorio.'))
            if not picking.lab_responsible_user_id:
                raise UserError(_('No hay responsable de laboratorio definido en este préstamo.'))
            if picking.env.user != picking.lab_responsible_user_id:
                raise UserError(_('Solo el usuario «Responsable (lab.)» puede aprobar el cierre de este préstamo.'))
            picking.write({
                'component_lab_pending_responsible_approval': False,
                'component_lab_loan_completed': True,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cierre aprobado'),
                'message': _('El préstamo pasa a la fase «Completado (devuelto)».'),
                'type': 'success',
                'sticky': False,
            },
        }

    def _action_done(self):
        res = super()._action_done()
        # En Odoo 19 el state del albarán es calculado: no pasa por write({'state': 'done'}).
        done_pick = self.filtered(lambda p: p.state == 'done')
        promote = done_pick.filtered(lambda p: p.component_lab_temp_out)
        pool_promote = promote.filtered(lambda p: p.component_lab_pool_intake)
        legacy_promote = promote - pool_promote
        if pool_promote:
            for p in pool_promote:
                p._component_lab_create_pool_assignments()
            pool_promote.write({'component_lab_temp_out': False})
        if legacy_promote:
            legacy_promote.write({
                'component_lab_loan_active': True,
                'component_lab_temp_out': False,
            })
        for ret in done_pick.filtered(lambda p: p.component_lab_source_loan_picking_id):
            src = ret.component_lab_source_loan_picking_id
            if not src:
                continue
            if src.component_lab_loan_active:
                src.write({
                    'component_lab_loan_active': False,
                    'component_lab_pending_responsible_approval': True,
                })
            elif not src.component_lab_loan_completed and not src.component_lab_pending_responsible_approval:
                src.write({'component_lab_pending_responsible_approval': True})
        return res

    def action_cancel(self):
        returns_before = self.filtered(lambda p: p.component_lab_source_loan_picking_id)
        had_temp = self.filtered(lambda p: p.component_lab_temp_out)
        res = super().action_cancel()
        if had_temp:
            had_temp.write({'component_lab_temp_out': False})

        cancelled = self.filtered(lambda p: p.state == 'cancel')
        cancelled_loan = cancelled.filtered(lambda p: p.component_lab_loan_active)
        if cancelled_loan:
            cancelled_loan.write({'component_lab_loan_active': False})

        for ret in (returns_before & cancelled):
            src = ret.component_lab_source_loan_picking_id
            if src.state == 'done':
                src.write({
                    'component_lab_loan_active': True,
                    'component_lab_loan_completed': False,
                    'component_lab_pending_responsible_approval': False,
                })
        return res
