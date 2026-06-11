# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ReturnRouteE4ClassificationWizard(models.TransientModel):
    _name = 'return.route.e4.classification.wizard'
    _description = 'Verificación E4 — devolución'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán E4',
        required=True,
        ondelete='cascade',
    )
    wizard_mode = fields.Selection(
        [
            ('logistics', 'Logística'),
            ('technician', 'Técnico'),
        ],
        string='Modo',
        default='logistics',
        required=True,
    )
    dictamen_progress = fields.Char(
        related='picking_id.invdash_return_e4_dictamen_progress',
        readonly=True,
    )
    line_ids = fields.One2many(
        'return.route.e4.classification.wizard.line',
        'wizard_id',
        string='Equipos',
    )

    def action_save_assignments(self):
        self.ensure_one()
        if self.wizard_mode != 'logistics' and not self.env.user.has_group(
            'stock.group_stock_manager'
        ):
            raise UserError(_('Solo logística puede asignar técnicos.'))
        updated = 0
        tickets_created = 0
        processed_anchors = set()
        for wl in self.line_ids.filtered(
            lambda l: l.dictamen_line_id.state != 'transferred'
        ):
            if not wl.technician_user_id:
                continue
            Dictamen = self.env['stock.picking.return.e4.dictamen.line']
            Dictamen._return_e4_validate_nivel1_technician(wl.technician_user_id)
            anchor = wl.dictamen_line_id._return_e4_group_anchor()
            if anchor.id in processed_anchors:
                continue
            processed_anchors.add(anchor.id)
            anchor._return_e4_propagate_technician_to_group(wl.technician_user_id)
            updated += len(anchor._return_e4_group_dictamen_lines())
        if not updated:
            raise UserError(_(
                'Indique el técnico en el equipo principal (propaga a todos sus asociados).'
            ))
        anchors = self.env['stock.picking.return.e4.dictamen.line'].browse(
            list(processed_anchors)
        )
        anchors._return_e4_ensure_helpdesk_ticket()
        tickets_created = len(processed_anchors)
        msg = _(
            'Asignación guardada: %(n)s equipo(s) en %(t)s ticket(s) (principal + asociados).'
        ) % {'n': updated, 't': tickets_created}
        if tickets_created:
            msg = _(
                '%(msg)s El técnico verifica cada serial desde el ticket.'
            ) % {'msg': msg}
        self.picking_id._return_e4_sync_dictamen_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asignación Técnicos'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_save_dictamen(self):
        self.ensure_one()
        is_manager = self.env.user.has_group('stock.group_stock_manager')
        updated = 0
        for wl in self.line_ids.filtered(
            lambda l: l.dictamen_line_id.state != 'transferred'
        ):
            if self.wizard_mode == 'technician' and not is_manager:
                if wl.technician_user_id != self.env.user:
                    continue
            if not wl.destination:
                raise UserError(_(
                    'Indique destino para el serial %s.'
                ) % (wl.lot_id.display_name or wl.lot_id.name))
            wl.dictamen_line_id.write({
                'destination': wl.destination,
                'dictamen_note': wl.dictamen_note or False,
            })
            wl.dictamen_line_id._set_state_from_values()
            updated += 1
        if not updated:
            raise UserError(_('No hay líneas de verificación para guardar.'))
        return self._reload_wizard_notification(
            _('Verificación guardada (%s línea(s)).') % updated,
        )

    def action_execute_transfers(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking._is_return_route_e4_picking():
            raise UserError(_('El albarán ya no es un E4 de devolución válido.'))

        if self.wizard_mode == 'logistics':
            to_run = self.line_ids.filtered(
                lambda l: l.dictamen_line_id.state == 'dictated' and l.destination
            )
            if not to_run:
                raise UserError(_(
                    'No hay equipos con destino verificado desde el ticket. '
                    'El técnico debe indicar destinos en el ticket E4 y marcarlo resuelto, '
                    'o completar la verificación antes de trasladar.'
                ))
        else:
            to_run = self.line_ids.filtered(
                lambda l: l.to_execute
                and l.dictamen_line_id.state == 'dictated'
                and l.destination
            )
            if not to_run:
                raise UserError(_(
                    'No hay líneas listas para trasladar. Complete la verificación desde el ticket E4.'
                ))

        dictamen_lines = to_run.mapped('dictamen_line_id')
        result = picking._return_e4_finalize_dictamen_transfer_batch(dictamen_lines)
        created_pickings = result['created_pickings']

        if picking.invdash_return_e4_all_dictamen_done:
            return {
                'type': 'ir.actions.act_window',
                'name': _('E4 devolución — completado'),
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }

        return self._reload_wizard_notification(
            _('Traslados ejecutados. %(progress)s') % {
                'progress': picking.invdash_return_e4_dictamen_progress or '',
            },
        )

    def action_confirm(self):
        """Compatibilidad: ejecuta traslado de todas las líneas dictaminadas marcadas."""
        for wl in self.line_ids:
            if wl.dictamen_line_id.state == 'dictated':
                wl.to_execute = True
        return self.action_execute_transfers()

    def _reload_wizard_notification(self, message):
        self.picking_id._return_e4_sync_dictamen_lines()
        new_wiz = self.picking_id._return_e4_open_classification_wizard(
            wizard_mode=self.wizard_mode,
        )
        new_wiz['context'] = dict(
            self.env.context,
            default_notification_message=message,
        )
        return new_wiz


class ReturnRouteE4ClassificationWizardLine(models.TransientModel):
    _name = 'return.route.e4.classification.wizard.line'
    _description = 'Línea verificación E4 devolución (wizard)'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'return.route.e4.classification.wizard',
        required=True,
        ondelete='cascade',
    )
    wizard_mode = fields.Selection(related='wizard_id.wizard_mode', readonly=True)
    dictamen_line_id = fields.Many2one(
        'stock.picking.return.e4.dictamen.line',
        string='Línea verificación',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    line_role = fields.Selection(related='dictamen_line_id.line_role', readonly=True)
    group_lot_id = fields.Many2one(
        'stock.lot',
        string='Conjunto',
        compute='_compute_group_lot_id',
    )
    principal_lot_id = fields.Many2one(
        related='dictamen_line_id.principal_lot_id',
        readonly=True,
    )
    lot_id = fields.Many2one(related='dictamen_line_id.lot_id', readonly=True)
    product_id = fields.Many2one(related='dictamen_line_id.product_id', readonly=True)
    quantity = fields.Float(related='dictamen_line_id.quantity', readonly=True)
    state = fields.Selection(related='dictamen_line_id.state', readonly=True)
    state_label = fields.Char(compute='_compute_state_label', string='Estado')
    technician_user_id = fields.Many2one(
        related='dictamen_line_id.technician_user_id',
        readonly=False,
        domain=lambda self: self.env[
            'stock.picking.return.e4.dictamen.line'
        ]._return_e4_nivel1_technician_domain(),
    )
    destination = fields.Selection(
        related='dictamen_line_id.destination',
        readonly=True,
    )
    dictamen_note = fields.Text(related='dictamen_line_id.dictamen_note', readonly=True)
    destination_label = fields.Char(
        related='dictamen_line_id.destination_label',
        readonly=True,
    )
    helpdesk_ticket_id = fields.Many2one(
        related='dictamen_line_id.helpdesk_ticket_id',
        readonly=True,
    )
    to_execute = fields.Boolean(
        string='Trasladar',
        default=False,
        help='Ejecutar traslado interno para esta línea (debe estar dictaminada).',
    )

    @api.depends('line_role', 'lot_id', 'principal_lot_id')
    def _compute_group_lot_id(self):
        for line in self:
            if line.line_role == 'associated' and line.principal_lot_id:
                line.group_lot_id = line.principal_lot_id
            else:
                line.group_lot_id = line.lot_id

    @api.depends('state')
    def _compute_state_label(self):
        labels = {
            'unassigned': _('Sin asignar'),
            'assigned': _('Asignado'),
            'dictated': _('Verificado'),
            'transferred': _('Trasladado'),
        }
        for line in self:
            line.state_label = labels.get(line.state, line.state or '')
