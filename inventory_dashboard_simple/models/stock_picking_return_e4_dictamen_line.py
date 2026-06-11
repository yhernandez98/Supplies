# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

RETURN_E4_DESTINATION_SELECTION = [
    ('stock', 'Existencias'),
    ('warranty', 'Garantía'),
    ('repair', 'Reparación'),
    ('scrap_initial', 'PreBaja'),
]


RETURN_E4_NIVEL1_TEAM_NAME = 'Nivel 1'


class StockPickingReturnE4DictamenLine(models.Model):
    _name = 'stock.picking.return.e4.dictamen.line'
    _description = 'Línea verificación E4 devolución'
    _order = 'state, principal_lot_id, line_role, id'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán E4',
        required=True,
        ondelete='cascade',
        index=True,
    )
    line_role = fields.Selection(
        [
            ('principal', 'Principal'),
            ('associated', 'Asociado'),
            ('bundled', 'Componente'),
            ('standalone', 'Serial'),
        ],
        string='Rol',
        required=True,
    )
    is_bundled_component = fields.Boolean(
        string='Componente empaquetado',
        compute='_compute_is_bundled_component',
        store=True,
    )
    principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial padre',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        related='lot_id.product_id',
        store=True,
        readonly=True,
    )
    quantity = fields.Float(string='Cantidad', default=1.0, readonly=True)
    technician_user_id = fields.Many2one(
        'res.users',
        string='Técnico',
        domain=lambda self: self._return_e4_nivel1_technician_domain(),
        tracking=True,
    )
    destination = fields.Selection(
        RETURN_E4_DESTINATION_SELECTION,
        string='Destino',
        tracking=True,
    )
    dictamen_note = fields.Text(string='Notas internas')
    state = fields.Selection(
        [
            ('unassigned', 'Sin asignar'),
            ('assigned', 'Asignado'),
            ('dictated', 'Verificado'),
            ('transferred', 'Trasladado'),
        ],
        string='Estado',
        default='unassigned',
        required=True,
        index=True,
    )
    internal_picking_id = fields.Many2one(
        'stock.picking',
        string='Traslado interno',
        readonly=True,
        copy=False,
    )
    destination_label = fields.Char(
        compute='_compute_destination_label',
        string='Destino',
    )

    _sql_constraints = [
        (
            'dictamen_lot_picking_uniq',
            'unique(picking_id, lot_id)',
            'Cada serial solo puede aparecer una vez en la verificación de este E4.',
        ),
    ]

    @api.depends('line_role')
    def _compute_is_bundled_component(self):
        for line in self:
            line.is_bundled_component = line.line_role == 'bundled'

    @api.depends('destination')
    def _compute_destination_label(self):
        labels = dict(RETURN_E4_DESTINATION_SELECTION)
        for line in self:
            line.destination_label = labels.get(line.destination, '') or ''

    @api.constrains('destination', 'state')
    def _check_destination_when_dictated(self):
        for line in self:
            if line.state in ('dictated', 'transferred') and not line.destination:
                raise ValidationError(_(
                    'El serial %s requiere destino en la verificación.'
                ) % (line.lot_id.display_name or line.lot_id.name))

    @api.model
    def _return_e4_get_nivel1_support_team(self):
        if 'helpdesk.team' not in self.env:
            return self.env['helpdesk.team']
        return self.env['helpdesk.team'].sudo().search([
            ('name', '=', RETURN_E4_NIVEL1_TEAM_NAME),
        ], limit=1)

    @api.model
    def _return_e4_ticket_team_and_stage_vals(self):
        """Equipo y etapa inicial para tickets de verificación E4."""
        team = self._return_e4_get_nivel1_support_team()
        if not team:
            raise ValidationError(_(
                'Configure el equipo de soporte «%(team)s» en Mesa de Ayuda → '
                'Configuración → Equipos de soporte.'
            ) % {'team': RETURN_E4_NIVEL1_TEAM_NAME})
        vals = {'team_id': team.id}
        Ticket = self.env['helpdesk.ticket']
        if hasattr(Ticket, '_mesa_followup_pick_open_stage'):
            stage = Ticket._mesa_followup_pick_open_stage(team=team)
            if stage:
                vals['stage_id'] = stage.id
        return vals

    @api.model
    def _return_e4_nivel1_technician_user_ids(self):
        team = self._return_e4_get_nivel1_support_team()
        members = getattr(team, 'member_ids', self.env['res.users'])
        return [uid for uid in members.ids if uid]

    @api.model
    def _return_e4_nivel1_technician_domain(self):
        user_ids = self._return_e4_nivel1_technician_user_ids()
        if user_ids:
            return [('id', 'in', user_ids)]
        return [('id', '=', False)]

    @api.model
    def _return_e4_validate_nivel1_technician(self, user):
        """Valida que el usuario pertenezca al equipo Nivel 1 (asignación E4)."""
        if not user:
            return
        allowed_ids = set(self._return_e4_nivel1_technician_user_ids())
        if not allowed_ids:
            raise ValidationError(_(
                'Configure el equipo de soporte «%(team)s» en Mesa de Ayuda → '
                'Configuración → Equipos de soporte y asigne al menos un miembro.'
            ) % {'team': RETURN_E4_NIVEL1_TEAM_NAME})
        if user.id not in allowed_ids:
            raise ValidationError(_(
                'El técnico «%(tech)s» no pertenece al equipo de soporte «%(team)s».'
            ) % {
                'tech': user.display_name,
                'team': RETURN_E4_NIVEL1_TEAM_NAME,
            })

    def _set_state_from_values(self):
        for line in self:
            if line.state == 'transferred':
                continue
            if line.destination:
                new_state = 'dictated'
            elif line.technician_user_id:
                new_state = 'assigned'
            else:
                new_state = 'unassigned'
            if line.state != new_state:
                line.write({'state': new_state})

    def write(self, vals):
        if (
            vals.get('technician_user_id')
            and not self.env.context.get('invdash_propagating_technician')
        ):
            self._return_e4_validate_nivel1_technician(
                self.env['res.users'].browse(vals['technician_user_id']),
            )
        res = super().write(vals)
        if vals.get('destination') and not self.env.context.get('invdash_propagating_dest'):
            principals = self.filtered(
                lambda l: l.line_role == 'principal' and l.destination,
            )
            for principal in principals:
                bundled = self.search([
                    ('picking_id', '=', principal.picking_id.id),
                    ('principal_lot_id', '=', principal.lot_id.id),
                    ('line_role', '=', 'bundled'),
                    ('state', '!=', 'transferred'),
                ])
                if bundled:
                    bundled.with_context(invdash_propagating_dest=True).write({
                        'destination': principal.destination,
                    })
                    bundled._set_state_from_values()
        return res

    @api.model
    def _return_e4_anchor_from_group_lines(self, group_lines):
        """Ancla (principal o standalone) desde un recordset de varias líneas del mismo grupo."""
        group_lines = group_lines.exists()
        if not group_lines:
            return self.env['stock.picking.return.e4.dictamen.line']
        principal = group_lines.filtered(lambda l: l.line_role == 'principal')[:1]
        if principal:
            return principal
        standalone = group_lines.filtered(lambda l: l.line_role == 'standalone')[:1]
        if standalone:
            return standalone
        return group_lines[:1]._return_e4_group_anchor()

    def _return_e4_group_anchor(self):
        """Línea principal del grupo (ticket único por equipo + asociados)."""
        self.ensure_one()
        if self.line_role in ('principal', 'standalone'):
            return self
        if not self.principal_lot_id:
            return self
        principal = self.picking_id.invdash_return_e4_dictamen_line_ids.filtered(
            lambda l: l.line_role == 'principal' and l.lot_id == self.principal_lot_id
        )[:1]
        return principal or self

    def _return_e4_group_dictamen_lines(self):
        """Principal + todos los asociados listados en el E4 para el mismo padre."""
        self.ensure_one()
        anchor = self._return_e4_group_anchor()
        if anchor.line_role == 'standalone':
            return anchor
        Dictamen = self.env['stock.picking.return.e4.dictamen.line']
        children = Dictamen.search([
            ('picking_id', '=', anchor.picking_id.id),
            ('principal_lot_id', '=', anchor.lot_id.id),
            ('line_role', 'in', ('associated', 'bundled')),
        ])
        return anchor | children

    def _return_e4_propagate_technician_to_group(self, technician):
        """Misma asignación de técnico para principal, asociados y componentes."""
        self.ensure_one()
        if self.env.context.get('invdash_propagating_technician'):
            return self._return_e4_group_dictamen_lines()
        if not technician:
            return self.env['stock.picking.return.e4.dictamen.line']
        anchor = self._return_e4_group_anchor()
        group = anchor._return_e4_group_dictamen_lines()
        pending = group.filtered(lambda l: l.state != 'transferred')
        if pending:
            pending.with_context(
                invdash_propagating_technician=True,
                invdash_skip_ticket_sync=True,
            ).write({'technician_user_id': technician.id})
            pending._set_state_from_values()
        return group

    def _return_e4_heal_group_consistency(self):
        """Corrige técnico/estado del principal si el grupo ya fue asignado."""
        Dictamen = self.env['stock.picking.return.e4.dictamen.line']
        anchors = Dictamen.browse(set(
            line._return_e4_group_anchor().id for line in self
        ))
        for anchor in anchors:
            group = anchor._return_e4_group_dictamen_lines()
            tech = anchor.technician_user_id or group.mapped('technician_user_id')[:1]
            if not tech and anchor.helpdesk_ticket_id:
                tech = anchor.helpdesk_ticket_id.user_id
            if tech:
                anchor._return_e4_propagate_technician_to_group(tech)
            principal = anchor if anchor.line_role == 'principal' else group.filtered(
                lambda l: l.line_role == 'principal',
            )[:1]
            if principal and principal.destination:
                principal.with_context(invdash_propagating_dest=True).write({
                    'destination': principal.destination,
                })
        return self
