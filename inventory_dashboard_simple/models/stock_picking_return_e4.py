# -*- coding: utf-8 -*-
"""Verificación E4 en rutas de devolución: destinos finales por ticket."""

import logging
import uuid

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero

_logger = logging.getLogger(__name__)

RETURN_E4_DESTINATION_LABELS = {
    'stock': 'Existencias',
    'warranty': 'Garantía',
    'repair': 'Reparación',
    'scrap_initial': 'PreBaja',
}

# Pistas de nombre de stock.picking.type por destino E4 (tras coincidencia exacta de ubicaciones).
RETURN_E4_CLASSIFICATION_PICKING_TYPE_NAME_HINTS = {
    'warranty': ('garantía', 'garantia'),
    'repair': ('reparación', 'reparacion'),
    'scrap_initial': ('prebaja', 'pre baja'),
}


class _ReturnE4ClassificationProcessLine:
    """Línea normalizada para ejecutar traslados (dictamen o componente empaquetado)."""

    __slots__ = (
        'lot', 'product', 'line_role', 'principal_lot', 'quantity', 'destination',
    )

    def __init__(self, lot, product, line_role, principal_lot, quantity, destination):
        self.lot = lot
        self.product = product
        self.line_role = line_role
        self.principal_lot = principal_lot
        self.quantity = quantity
        self.destination = destination


class StockPickingReturnE4(models.Model):
    _inherit = 'stock.picking'

    invdash_return_e4_classified = fields.Boolean(
        string='E4 verificado',
        default=False,
        copy=False,
        index=True,
        help='Tras clasificar destinos desde Verificación, el albarán E4 de la ruta puede cerrarse.',
    )
    invdash_return_e4_classification_picking_ids = fields.Many2many(
        'stock.picking',
        'stock_picking_return_e4_classif_rel',
        'route_e4_picking_id',
        'internal_picking_id',
        string='Traslados internos E4',
        copy=False,
        readonly=True,
    )
    invdash_show_return_e4_classify_button = fields.Boolean(
        compute='_compute_invdash_show_return_e4_classify_button',
    )
    invdash_is_return_e4_classification = fields.Boolean(
        string='Traslado interno E4',
        default=False,
        copy=False,
        help='Traslado interno generado por la verificación E4 de devolución.',
    )
    invdash_return_e4_classified_line_ids = fields.One2many(
        'stock.picking.return.e4.classified.line',
        'picking_id',
        string='Historial traslados E4',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_show_classified_archive = fields.Boolean(
        compute='_compute_invdash_return_e4_show_classified_archive',
    )
    invdash_return_e4_dictamen_line_ids = fields.One2many(
        'stock.picking.return.e4.dictamen.line',
        'picking_id',
        string='Líneas verificación E4',
        copy=False,
    )
    invdash_return_e4_dictamen_progress = fields.Char(
        string='Progreso verificación E4',
        compute='_compute_invdash_return_e4_dictamen_progress',
    )
    invdash_return_e4_all_dictamen_done = fields.Boolean(
        compute='_compute_invdash_return_e4_dictamen_progress',
    )
    invdash_show_return_e4_my_dictamen_button = fields.Boolean(
        compute='_compute_invdash_show_return_e4_my_dictamen_button',
    )

    @api.depends(
        'invdash_return_e4_dictamen_line_ids',
        'invdash_return_e4_dictamen_line_ids.state',
    )
    def _compute_invdash_return_e4_dictamen_progress(self):
        for picking in self:
            lines = picking.invdash_return_e4_dictamen_line_ids
            total = len(lines)
            if not total:
                picking.invdash_return_e4_dictamen_progress = ''
                picking.invdash_return_e4_all_dictamen_done = False
                continue
            dictated = len(lines.filtered(lambda l: l.state in ('dictated', 'transferred')))
            transferred = len(lines.filtered(lambda l: l.state == 'transferred'))
            picking.invdash_return_e4_dictamen_progress = _(
                '%(dictated)s/%(total)s verificados · %(transferred)s/%(total)s trasladados'
            ) % {
                'dictated': dictated,
                'transferred': transferred,
                'total': total,
            }
            picking.invdash_return_e4_all_dictamen_done = transferred == total

    @api.depends(
        'invdash_return_e4_dictamen_line_ids',
        'invdash_return_e4_dictamen_line_ids.state',
        'invdash_return_e4_dictamen_line_ids.technician_user_id',
        'state',
    )
    def _compute_invdash_show_return_e4_my_dictamen_button(self):
        uid = self.env.user.id
        for picking in self:
            picking.invdash_show_return_e4_my_dictamen_button = bool(
                picking._is_return_route_e4_picking()
                and picking.state not in ('done', 'cancel')
                and picking.invdash_return_e4_dictamen_line_ids.filtered(
                    lambda l: l.technician_user_id.id == uid
                    and l.state in ('assigned', 'dictated')
                )
            )

    @api.depends(
        'invdash_return_e4_classified',
        'invdash_return_e4_classified_line_ids',
        'invdash_return_e4_classification_picking_ids',
        'invdash_return_e4_dictamen_line_ids.state',
        'move_line_ids',
        'move_line_ids.supply_kind',
        'origin',
        'location_id',
        'location_dest_id',
    )
    def _compute_invdash_return_e4_show_classified_archive(self):
        for picking in self:
            show = False
            if picking._is_return_route_e4_picking() and (
                picking.invdash_return_e4_classified
                or picking.invdash_return_e4_classified_line_ids
                or picking.invdash_return_e4_dictamen_line_ids.filtered(
                    lambda l: l.state == 'transferred'
                )
            ):
                main_lines = picking.move_line_ids.filtered(
                    lambda ml: getattr(ml, 'supply_kind', None) == 'parent'
                )
                show = bool(picking.invdash_return_e4_classified_line_ids) or not main_lines
            picking.invdash_return_e4_show_classified_archive = show

    @api.depends(
        'state',
        'origin',
        'location_id',
        'location_dest_id',
        'invdash_return_e4_all_dictamen_done',
        'invdash_return_e4_dictamen_line_ids.state',
    )
    def _compute_invdash_show_return_e4_classify_button(self):
        for picking in self:
            picking.invdash_show_return_e4_classify_button = (
                picking._is_return_route_e4_picking()
                and picking.state not in ('done', 'cancel')
                and not picking.invdash_return_e4_all_dictamen_done
            )

    def _location_name_has(self, location, *tokens):
        if not location:
            return False
        name = (location.complete_name or location.name or '').lower()
        return any(token in name for token in tokens)

    def _picking_is_devolucion_to_verificacion(self):
        """E3 devolución: Supp/Devolución → Supp/Verificación."""
        self.ensure_one()
        if not self.location_id or not self.location_dest_id:
            return False
        return (
            self._location_name_has(self.location_id, 'devolución', 'devolucion')
            and self._location_name_has(self.location_dest_id, 'verificación', 'verificacion')
        )

    def _picking_is_return_route_e4_by_locations(self):
        """E4 devolución: sale DE Verificación hacia destino final (no hacia Verificación)."""
        self.ensure_one()
        if not self.location_id or not self.location_dest_id:
            return False
        if not self._location_name_has(self.location_id, 'verificación', 'verificacion'):
            return False
        if self._location_name_has(self.location_dest_id, 'verificación', 'verificacion'):
            return False
        return True

    def _infer_return_route_stage_from_locations(self):
        """Etapa de ruta de devolución por ubicaciones (prioridad sobre origin mal numerado)."""
        self.ensure_one()
        if self.invdash_is_return_e4_classification:
            return 0
        if self._picking_is_return_route_e4_by_locations():
            return 4
        if self._picking_is_devolucion_to_verificacion():
            return 3
        if (
            self.location_id and self.location_dest_id
            and self._location_name_has(self.location_id, 'transporte', 'transito', 'tránsito')
            and self._location_name_has(self.location_dest_id, 'devolución', 'devolucion')
        ):
            return 2
        if (
            self.location_id and self.location_dest_id
            and hasattr(self, '_is_client_stock_location')
            and self._is_client_stock_location(self.location_id)
            and self._location_name_has(self.location_dest_id, 'transporte', 'transito', 'tránsito')
        ):
            return 1
        return 0

    def _is_return_route_e4_picking(self):
        """Albarán E4 de ruta de devolución: Verificación → destino final."""
        self.ensure_one()
        if self.invdash_is_return_e4_classification:
            return False
        if not self._origin_is_return_route():
            return False
        if self._picking_is_devolucion_to_verificacion():
            return False
        if self._picking_is_return_route_e4_by_locations():
            return True
        if self._is_route_wizard_origin(self.origin):
            return self._route_stage_from_origin(self.origin or '') == 4
        return False

    def _return_e4_verification_location(self):
        self.ensure_one()
        if self.location_id:
            return self.location_id
        return self.env['return.route.location']._find_location_by_complete_name_fragment(
            'Supp/Verificación',
        )

    def _return_e4_is_component_associate(self, related_lot, supply_line=None):
        """True si el asociado es clasificación Componente (producto o línea de suministro)."""
        if supply_line and supply_line.item_type == 'component':
            return True
        classification = getattr(related_lot, 'lot_classification', None)
        if not classification and related_lot.product_id:
            classification = getattr(related_lot.product_id, 'classification', None)
        return classification == 'component'

    def _return_e4_is_additional_cost_component(self, supply_line, related_lot):
        """Componente en pestaña con costo + serial con Costo Adicional activo."""
        return bool(
            supply_line
            and supply_line.has_cost
            and getattr(related_lot, 'cost_additional', False)
        )

    def _return_e4_should_list_associated_in_wizard(self, supply_line, related_lot):
        """
        En E4 se listan periféricos/complementos/etc.
        Los componentes van con el principal salvo que sean costo adicional.
        """
        if not related_lot:
            return False
        if not self._return_e4_is_component_associate(related_lot, supply_line):
            return True
        return self._return_e4_is_additional_cost_component(supply_line, related_lot)

    def _return_e4_bundled_component_destinations(self, wizard_lines):
        """
        Componentes sin costo adicional: heredan destino del principal
        (no aparecen en grilla, pero se mueven al confirmar).
        Retorna listas de dict compatibles con líneas del wizard.
        """
        self.ensure_one()
        principal_dest = {
            line.lot_id.id: line.destination
            for line in wizard_lines
            if line.line_role == 'principal' and line.lot_id
        }
        seen_lot_ids = set(wizard_lines.mapped('lot_id').ids)
        bundled = []
        for principal_id, destination in principal_dest.items():
            principal = self.env['stock.lot'].browse(principal_id)
            if not principal.exists():
                continue
            for sl in principal.lot_supply_line_ids.filtered('related_lot_id'):
                related = sl.related_lot_id
                if not related or related.id == principal.id or related.id in seen_lot_ids:
                    continue
                if self._return_e4_should_list_associated_in_wizard(sl, related):
                    continue
                seen_lot_ids.add(related.id)
                bundled.append({
                    'lot_id': related.id,
                    'product_id': related.product_id.id,
                    'line_role': 'associated',
                    'principal_lot_id': principal.id,
                    'quantity': 1.0,
                    'destination': destination,
                    'supply_line_id': sl.id,
                })
        return bundled

    def _return_e4_bundled_lots_for_principal(self, principal_lot, exclude_lot_ids=None):
        """Componentes que van con el principal (no listados en grilla E4) para el ticket."""
        self.ensure_one()
        if not principal_lot:
            return []
        exclude = set(exclude_lot_ids or [])
        rows = []
        for sl in principal_lot.lot_supply_line_ids.filtered('related_lot_id'):
            related = sl.related_lot_id
            if not related or related.id == principal_lot.id or related.id in exclude:
                continue
            if self._return_e4_should_list_associated_in_wizard(sl, related):
                continue
            rows.append({
                'lot': related,
                'principal_lot': principal_lot,
            })
        return rows

    def _return_e4_classification_lot_rows(self):
        """Filas para el wizard: principal + asociados (filtrados) + seriales sueltos."""
        self.ensure_one()
        rows = []
        seen_lot_ids = set()

        def _add_row(lot, role, principal_lot=None):
            if not lot or lot.id in seen_lot_ids:
                return
            seen_lot_ids.add(lot.id)
            rows.append({
                'lot_id': lot.id,
                'product_id': lot.product_id.id,
                'line_role': role,
                'principal_lot_id': principal_lot.id if principal_lot else False,
                'quantity': 1.0,
                'destination': 'stock',
            })

        principal_lots = self.env['stock.lot']
        for ml in self.move_line_ids.filtered(lambda m: m.lot_id):
            lot = ml.lot_id
            if lot.product_id.tracking != 'serial':
                continue
            is_parent = (
                hasattr(ml.move_id, 'supply_kind')
                and ml.move_id.supply_kind == 'parent'
            )
            has_associates = bool(
                hasattr(lot, 'lot_supply_line_ids')
                and lot.lot_supply_line_ids.filtered('related_lot_id')
            )
            if is_parent or has_associates:
                principal_lots |= lot

        associated_ids = set()
        for principal in principal_lots:
            _add_row(principal, 'principal')
            if hasattr(principal, 'lot_supply_line_ids'):
                for sl in principal.lot_supply_line_ids.filtered('related_lot_id'):
                    related = sl.related_lot_id
                    if not related or related.id == principal.id:
                        continue
                    if self._return_e4_should_list_associated_in_wizard(sl, related):
                        associated_ids.add(related.id)
                        _add_row(related, 'associated', principal_lot=principal)
                    elif self._return_e4_is_component_associate(related, sl):
                        _add_row(related, 'bundled', principal_lot=principal)

        for ml in self.move_line_ids.filtered(lambda m: m.lot_id):
            lot = ml.lot_id
            if lot.product_id.tracking != 'serial':
                continue
            if lot.id in seen_lot_ids:
                continue
            _add_row(lot, 'standalone')

        if not rows:
            for lot in self._billing_serial_lots():
                _add_row(lot, 'standalone')
        return rows

    def _return_e4_sync_dictamen_lines(self):
        """Crea o actualiza líneas de dictamen según seriales del E4 (sin tocar trasladados)."""
        self.ensure_one()
        Dictamen = self.env['stock.picking.return.e4.dictamen.line']
        rows = self._return_e4_classification_lot_rows()
        existing = Dictamen.search([('picking_id', '=', self.id)])
        by_lot = {dl.lot_id.id: dl for dl in existing}
        for row in rows:
            lot_id = row['lot_id']
            if lot_id in by_lot:
                dl = by_lot[lot_id]
                if dl.state == 'transferred':
                    continue
                dl.write({
                    'line_role': row['line_role'],
                    'principal_lot_id': row.get('principal_lot_id') or False,
                    'quantity': row.get('quantity') or 1.0,
                })
            else:
                Dictamen.create({
                    'picking_id': self.id,
                    'lot_id': lot_id,
                    'line_role': row['line_role'],
                    'principal_lot_id': row.get('principal_lot_id') or False,
                    'quantity': row.get('quantity') or 1.0,
                })
        lines = Dictamen.search([('picking_id', '=', self.id)])
        if self.invdash_return_e4_classified and lines.filtered(
            lambda l: l.state != 'transferred'
        ):
            archive_dest = {
                cl.lot_id.id: cl.destination
                for cl in self.invdash_return_e4_classified_line_ids
            }
            for dl in lines.filtered(lambda l: l.state != 'transferred'):
                dl.write({
                    'destination': archive_dest.get(dl.lot_id.id) or 'stock',
                    'state': 'transferred',
                })
        return lines

    def _return_e4_dictamen_to_processing_lines(self, dictamen_lines):
        self.ensure_one()
        lines = []
        for dl in dictamen_lines:
            if not dl.lot_id or not dl.destination:
                continue
            principal = dl.principal_lot_id
            lines.append(_ReturnE4ClassificationProcessLine(
                lot=dl.lot_id,
                product=dl.product_id or dl.lot_id.product_id,
                line_role=dl.line_role,
                principal_lot=principal,
                quantity=dl.quantity,
                destination=dl.destination,
            ))
        bundled = self._return_e4_bundled_component_destinations(dictamen_lines)
        Lot = self.env['stock.lot']
        Product = self.env['product.product']
        for row in bundled:
            lot = Lot.browse(row['lot_id'])
            lines.append(_ReturnE4ClassificationProcessLine(
                lot=lot,
                product=Product.browse(row['product_id']) if row.get('product_id') else lot.product_id,
                line_role=row.get('line_role') or 'associated',
                principal_lot=Lot.browse(row['principal_lot_id']) if row.get('principal_lot_id') else Lot.browse(),
                quantity=row.get('quantity') or 1.0,
                destination=row['destination'],
            ))
        return lines

    def _return_e4_link_dictamen_transferred(
        self, dictamen_lines, created_pickings, lot_picking_map=None,
    ):
        lot_picking_map = lot_picking_map or {}
        for dl in dictamen_lines:
            internal = lot_picking_map.get(dl.lot_id.id)
            if not internal:
                internal = created_pickings.filtered(
                    lambda p: p.move_line_ids.filtered(
                        lambda ml: ml.lot_id == dl.lot_id,
                    ),
                )[:1]
            if not internal and dl.principal_lot_id:
                internal = lot_picking_map.get(dl.principal_lot_id.id)
            if not internal and dl.principal_lot_id:
                internal = created_pickings.filtered(
                    lambda p: p.move_line_ids.filtered(
                        lambda ml: ml.lot_id == dl.principal_lot_id,
                    ),
                )[:1]
            dl.write({
                'state': 'transferred',
                'internal_picking_id': internal.id if internal else False,
            })

    def _return_e4_finalize_dictamen_transfer_batch(self, dictamen_lines):
        """
        Ejecuta traslados internos para líneas dictaminadas, archiva y cierra E4 si corresponde.
        Usado por el wizard de logística y por el cierre del ticket del técnico.
        """
        self.ensure_one()
        Picking = self.sudo() if self.env.context.get('invdash_return_e4_from_ticket') else self
        dictamen_lines = dictamen_lines.filtered(lambda l: l.picking_id == self)
        pending = dictamen_lines.filtered(lambda l: l.state != 'transferred')
        if not pending:
            return {
                'created_pickings': self.env['stock.picking'],
                'dictamen_lines': dictamen_lines,
                'processing_lines': [],
            }
        missing_dest = pending.filtered(lambda l: not l.destination)
        if missing_dest:
            labels = ', '.join(
                (l.lot_id.display_name or l.lot_id.name or '?')
                for l in missing_dest[:10]
            )
            raise UserError(_(
                'Faltan destinos en la verificación E4 para:\n%s'
            ) % labels)
        processing_lines = Picking._return_e4_dictamen_to_processing_lines(pending)
        if not processing_lines:
            raise UserError(_('No hay traslados E4 que ejecutar para las líneas indicadas.'))
        created_pickings, _disassociated, lot_picking_map = (
            Picking._return_e4_execute_classification_processing_lines(
                processing_lines,
            )
        )
        Picking._return_e4_link_dictamen_transferred(
            pending, created_pickings, lot_picking_map=lot_picking_map,
        )
        Picking._archive_return_e4_classification_lines(processing_lines)
        link_cmds = [(4, pid) for pid in created_pickings.ids]
        write_vals = {'invdash_return_e4_classified': True}
        if link_cmds:
            write_vals['invdash_return_e4_classification_picking_ids'] = link_cmds
        Picking.write(write_vals)
        Picking.message_post(body=_(
            'Traslado E4: %(count)s equipo(s). Progreso: %(progress)s'
        ) % {
            'count': len(pending),
            'progress': Picking.invdash_return_e4_dictamen_progress or '',
        })
        if Picking.invdash_return_e4_all_dictamen_done:
            Picking.message_post(body=_(
                'Verificación E4 completada al 100%%. Se cierra el albarán de ruta.'
            ))
            Picking._complete_return_e4_route_picking_after_classification()
        return {
            'created_pickings': created_pickings,
            'dictamen_lines': pending,
            'processing_lines': processing_lines,
        }

    def _return_e4_execute_classification_processing_lines(self, processing_lines):
        """Traslados internos por destino para las líneas indicadas."""
        self.ensure_one()
        if not processing_lines:
            raise UserError(_('No hay líneas para trasladar.'))

        source = self._return_e4_verification_location()
        if not source:
            raise UserError(_('No se pudo determinar la ubicación Supp/Verificación.'))

        LocHelper = self.env['return.route.location']
        dest_by_code = LocHelper.get_return_e4_destination_locations()
        Quant = self.env['stock.quant'].sudo()

        lots = self.env['stock.lot'].concat(*[line.lot for line in processing_lines if line.lot])
        affected_route_moves = self._return_e4_release_route_lots_for_transfer(lots)
        self._return_e4_free_lot_reservations(lots, exclude_pickings=self)

        allowed_sources = self._return_e4_allowed_source_locations()
        seen_lots = set()
        missing_stock = []
        for line in processing_lines:
            if not line.lot or not line.lot.id:
                raise UserError(_('Hay una línea sin número de serie válido.'))
            lot_label = line.lot.name or line.lot.display_name
            if line.lot.id in seen_lots:
                raise UserError(_('El serial %s está repetido en la grilla.') % lot_label)
            seen_lots.add(line.lot.id)
            if float_is_zero(line.quantity, precision_digits=2):
                raise UserError(_('La cantidad del serial %s debe ser mayor que cero.') % lot_label)
            if not dest_by_code.get(line.destination):
                raise UserError(_('Destino no válido para %s.') % lot_label)
            available = self._return_e4_lot_available_qty(line.lot, allowed_sources)
            if float_compare(line.quantity, available, precision_digits=2) > 0:
                q = Quant.search([
                    ('lot_id', '=', line.lot.id),
                    ('quantity', '>', 0),
                ], limit=1)
                where = q.location_id.complete_name if q else _('sin stock')
                missing_stock.append('%s (%s)' % (lot_label, where))
        if missing_stock:
            raise UserError(_(
                'No hay stock disponible en Verificación/Devolución para:\n%s\n\n'
                'Valide la etapa E3 (Devolución → Verificación) antes de clasificar E4.'
            ) % '\n'.join(missing_stock[:15]))

        from collections import defaultdict
        principal_dest_by_lot_id = {
            line.lot.id: line.destination
            for line in processing_lines
            if line.line_role == 'principal' and line.lot
        }

        grouped = defaultdict(list)
        for line in processing_lines:
            dest_loc = dest_by_code[line.destination]
            src_loc = self._return_e4_lot_source_location(line.lot, source)
            grouped[(src_loc.id, dest_loc.id)].append((line, src_loc, dest_loc))

        created_pickings = self.env['stock.picking']
        lot_picking_map = {}
        origin_label = self.origin or self.name

        with self.env.cr.savepoint():
            for (src_id, dest_id), entries in grouped.items():
                src_loc = entries[0][1]
                dest_loc = entries[0][2]
                lines = [e[0] for e in entries]
                picking_type = self._get_return_e4_classification_picking_type(
                    src_loc, dest_loc,
                )
                serials_note = ', '.join(
                    (line.lot.name or line.lot.display_name)
                    for line in lines if line.lot
                )
                internal = self._return_e4_create_classification_picking(
                    picking_type,
                    {
                        'picking_type_id': picking_type.id,
                        'location_id': src_loc.id,
                        'location_dest_id': dest_loc.id,
                        'origin': _('Traslado E4 devolución — %s') % origin_label,
                        'note': _('Generado desde %s. Seriales: %s') % (
                            self.display_name or self.name,
                            serials_note,
                        ),
                        'invdash_is_return_e4_classification': True,
                    },
                )
                lot_move_map = self._return_e4_create_classification_moves(
                    internal, lines, src_loc, dest_loc,
                )
                self.with_context(
                    invdash_return_e4_lot_move_map=lot_move_map,
                )._validate_return_e4_classification_picking(internal, lines)
                created_pickings |= internal
                for line in lines:
                    if line.lot:
                        lot_picking_map[line.lot.id] = internal

        disassociated_items = []
        seen_disassociate = set()
        for pl in processing_lines:
            if pl.line_role != 'associated' or not pl.principal_lot or not pl.lot:
                continue
            principal_dest = principal_dest_by_lot_id.get(pl.principal_lot.id)
            if not principal_dest or principal_dest == pl.destination:
                continue
            key = (pl.principal_lot.id, pl.lot.id)
            if key in seen_disassociate:
                continue
            seen_disassociate.add(key)
            if self._return_e4_disassociate_supply_line(pl.principal_lot, pl.lot):
                disassociated_items.append((
                    pl.principal_lot.display_name,
                    pl.lot.display_name,
                    pl.destination,
                ))

        if disassociated_items:
            self.message_post(
                body=self._return_e4_disassociation_chatter_body(disassociated_items),
                subtype_xmlid='mail.mt_note',
            )
        self._return_e4_finalize_route_after_partial_transfer(lots, affected_route_moves)
        return created_pickings, disassociated_items, lot_picking_map

    def _return_e4_resolve_ticket_partner(self, lot=None):
        """Cliente para ticket E4: albarán de ruta → serial → suscripción."""
        self.ensure_one()
        Lot = self.env['stock.lot']
        lot = lot or Lot

        def _commercial(partner):
            if not partner:
                return self.env['res.partner']
            return partner.commercial_partner_id or partner

        if self.partner_id:
            return _commercial(self.partner_id)

        if lot:
            if getattr(lot, 'customer_id', None) and lot.customer_id:
                return _commercial(lot.customer_id)
            subscription = getattr(lot, 'active_subscription_id', None)
            if subscription and subscription.partner_id:
                return _commercial(subscription.partner_id)
            if getattr(lot, 'related_partner_id', None) and lot.related_partner_id:
                related = lot.related_partner_id
                if related.parent_id:
                    return _commercial(related.parent_id)
                return _commercial(related)

        return self.env['res.partner']

    def _return_e4_sort_dictamen_lines(self, dictamen_lines):
        """Principal primero y luego sus asociados, agrupados por conjunto."""
        role_rank = {'principal': 0, 'standalone': 1, 'associated': 2, 'bundled': 3}

        def _sort_key(dl):
            if dl.line_role in ('associated', 'bundled') and dl.principal_lot_id:
                group_lot_id = dl.principal_lot_id.id
            else:
                group_lot_id = dl.lot_id.id
            return (
                group_lot_id or 0,
                role_rank.get(dl.line_role, 9),
                (dl.lot_id.name or dl.lot_id.display_name or ''),
                dl.id,
            )

        return dictamen_lines.sorted(key=_sort_key)

    def _return_e4_open_classification_wizard(self, wizard_mode='logistics'):
        self.ensure_one()
        if not self._is_return_route_e4_picking():
            raise UserError(_('Este albarán no es la etapa E4 de una ruta de devolución.'))
        if self.state in ('done', 'cancel'):
            raise UserError(_('El albarán ya está cerrado o cancelado.'))
        if self.invdash_return_e4_all_dictamen_done:
            raise UserError(_('Todos los equipos de este E4 ya fueron verificados y trasladados.'))
        e3 = self._route_picking_for_stage(3)
        if e3 and e3.state != 'done':
            raise UserError(_(
                'Valide antes la etapa E3 (Devolución → Verificación): %s.'
            ) % (e3.display_name or e3.name))

        dictamen_lines = self._return_e4_sync_dictamen_lines()
        if not dictamen_lines:
            raise UserError(_(
                'No hay números de serie en este albarán para clasificar. '
                'Reserve los seriales y vuelva a intentar.'
            ))

        Dictamen = self.env['stock.picking.return.e4.dictamen.line']
        domain = [
            ('picking_id', '=', self.id),
            ('state', '!=', 'transferred'),
        ]
        is_manager = self.env.user.has_group('stock.group_stock_manager')
        if wizard_mode == 'technician' and not is_manager:
            domain.append(('technician_user_id', '=', self.env.user.id))
        pending = Dictamen.search(domain)
        if not pending:
            raise UserError(_(
                'No hay equipos pendientes de verificación para usted en este albarán.'
            ))
        pending = self._return_e4_sort_dictamen_lines(pending)

        Wizard = self.env['return.route.e4.classification.wizard']
        wiz = Wizard.create({
            'picking_id': self.id,
            'wizard_mode': wizard_mode,
            'line_ids': [
                (0, 0, {
                    'dictamen_line_id': dl.id,
                    'sequence': (seq + 1) * 10,
                    'to_execute': dl.state == 'dictated',
                })
                for seq, dl in enumerate(pending)
            ],
        })
        title = _('Asignación Técnicos') if wizard_mode == 'logistics' else _('Tickets')
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'return.route.e4.classification.wizard',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_return_e4_classification_wizard(self):
        self.ensure_one()
        return self._return_e4_open_classification_wizard(wizard_mode='logistics')

    def action_open_return_e4_my_dictamen_tickets(self):
        """Lista de tickets de verificación ligados a este albarán E4."""
        self.ensure_one()
        if not self._is_return_route_e4_picking():
            raise UserError(_('Este albarán no es la etapa E4 de una ruta de devolución.'))

        domain = [
            ('invdash_return_e4_is_dictamen_ticket', '=', True),
            ('invdash_return_e4_picking_id', '=', self.id),
        ]
        if not self.env.user.has_group('stock.group_stock_manager'):
            domain.append(('user_id', '=', self.env.user.id))

        tickets = self.env['helpdesk.ticket'].search(domain, order='id desc')
        if not tickets:
            raise UserError(_(
                'No hay tickets de verificación para este albarán E4. '
                'Use «Asignación Técnicos» para asignar técnicos y generar tickets.'
            ))

        action = self.env.ref(
            'inventory_dashboard_simple.action_return_e4_my_dictamen_tickets',
            raise_if_not_found=False,
        )
        if not action:
            raise UserError(_('No está configurada la acción de tickets E4.'))

        result = action.read()[0]
        result['name'] = _('Tickets — %s') % (self.display_name or self.name)
        result['domain'] = domain
        result['context'] = dict(
            self.env.context,
            default_invdash_return_e4_picking_id=self.id,
        )
        result['view_mode'] = 'list,form'
        return result

    def action_open_return_e4_my_dictamen_wizard(self):
        """Abre los tickets de este albarán E4 (no todos los del usuario)."""
        self.ensure_one()
        return self.action_open_return_e4_my_dictamen_tickets()

    def _return_e4_allowed_source_locations(self):
        """Ubicaciones Supp desde las que se puede clasificar (verificación y etapas previas)."""
        self.ensure_one()
        Location = self.env['stock.location'].sudo()
        verif = self._return_e4_verification_location()
        allowed = verif
        if verif:
            allowed |= Location.search([('id', 'child_of', verif.id)])
        for fragment in ('Supp/Devolución', 'Supp/Devolucion', 'Supp/Verificación', 'Supp/Verificacion'):
            loc = self.env['return.route.location']._find_location_by_complete_name_fragment(fragment)
            if loc:
                allowed |= loc
                allowed |= Location.search([('id', 'child_of', loc.id)])
        return allowed

    def _return_e4_lot_source_location(self, lot, default_source):
        """Ubicación real del quant (p. ej. Devolución si el asociado no llegó a Verificación)."""
        self.ensure_one()
        Location = self.env['stock.location'].sudo()
        allowed = self._return_e4_allowed_source_locations()
        if not allowed:
            return default_source
        scope_ids = Location.search([('id', 'child_of', allowed.ids)]).ids
        quant = self.env['stock.quant'].sudo().search([
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
            ('location_id', 'in', scope_ids),
        ], order='quantity desc', limit=1)
        return quant.location_id if quant else default_source

    def _return_e4_lot_available_qty(self, lot, source_locations):
        Quant = self.env['stock.quant'].sudo()
        return sum(Quant.search([
            ('location_id', 'in', source_locations.ids),
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
        ]).mapped('quantity'))

    def _return_e4_free_lot_reservations(self, lots, exclude_pickings=None):
        """Libera reservas en otros albaranes (sin borrar líneas del E4 de ruta)."""
        if not lots:
            return
        exclude_pickings = exclude_pickings or self.env['stock.picking']
        MoveLine = self.env['stock.move.line'].sudo()
        lines = MoveLine.search([
            ('lot_id', 'in', lots.ids),
            ('state', 'not in', ('done', 'cancel')),
            ('picking_id', 'not in', exclude_pickings.ids),
            ('picking_id.state', 'not in', ('done', 'cancel')),
        ])
        moves = lines.move_id.filtered(lambda m: m.state not in ('done', 'cancel'))
        if moves and hasattr(moves, '_do_unreserve'):
            moves._do_unreserve()

    def _return_e4_picking_type_name_hints_for_dest(self, dest_loc):
        """Nombres esperados de tipo interno según ubicación destino E4."""
        LocHelper = self.env['return.route.location']
        try:
            dest_by_code = LocHelper.get_return_e4_destination_locations()
        except UserError:
            return ()
        for code, loc in dest_by_code.items():
            if loc.id == dest_loc.id:
                return RETURN_E4_CLASSIFICATION_PICKING_TYPE_NAME_HINTS.get(code, ())
        return ()

    def _get_return_e4_classification_picking_type(self, source_loc, dest_loc):
        """Tipo interno según par origen→destino (evita usar Garantía para ir a Existencias)."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type']
        company = self.company_id.id or self.env.company.id
        domain_base = [('code', '=', 'internal'), ('company_id', '=', company)]
        picking_type = PickingType.search(
            domain_base + [
                ('default_location_src_id', '=', source_loc.id),
                ('default_location_dest_id', '=', dest_loc.id),
            ],
            limit=1,
        )
        if picking_type:
            return picking_type
        for hint in self._return_e4_picking_type_name_hints_for_dest(dest_loc):
            picking_type = PickingType.search(
                domain_base + [
                    ('name', 'ilike', hint),
                    ('default_location_src_id', '=', source_loc.id),
                    ('default_location_dest_id', '=', dest_loc.id),
                ],
                limit=1,
            )
            if picking_type:
                return picking_type
        picking_type = PickingType.search(
            domain_base + [
                ('name', 'ilike', 'Verificación'),
                ('default_location_dest_id', '=', dest_loc.id),
            ],
            limit=1,
        )
        if picking_type:
            return picking_type
        if (
            self.picking_type_id
            and self.picking_type_id.code == 'internal'
            and self.location_id == source_loc
            and self.location_dest_id == dest_loc
        ):
            return self.picking_type_id
        wh = self.picking_type_id.warehouse_id if self.picking_type_id else False
        if not wh:
            wh = PickingType.search(domain_base, limit=1).warehouse_id
        if wh and wh.int_type_id:
            return wh.int_type_id
        raise UserError(_(
            'No hay tipo de operación interno configurado para %(src)s → %(dest)s.\n'
            'Cree un tipo interno con esas ubicaciones por defecto en Inventario → Tipos de operación.'
        ) % {'src': source_loc.display_name, 'dest': dest_loc.display_name})

    @api.model
    def _return_e4_picking_name_is_placeholder(self, name):
        if not name:
            return True
        if name in ('/', 'New'):
            return True
        return False

    @api.model
    def _return_e4_picking_name_looks_weak(self, name):
        """Secuencias mal configuradas (p. ej. solo «53») sin prefijo de albarán."""
        if not name or self._return_e4_picking_name_is_placeholder(name):
            return True
        stripped = (name or '').strip()
        if stripped.isdigit():
            return True
        return False

    @api.model
    def _return_e4_format_picking_label(self, picking):
        """Etiqueta legible para chatter/resumen E4."""
        if not picking:
            return '—'
        name = (picking.name or '').strip()
        if (
            name
            and not self._return_e4_picking_name_is_placeholder(name)
            and not self._return_e4_picking_name_looks_weak(name)
        ):
            return name
        picking_type = picking.picking_type_id.display_name or picking.picking_type_id.name
        if name and not self._return_e4_picking_name_is_placeholder(name):
            if picking_type:
                return '%s — %s' % (picking_type, name)
            return name
        return picking.display_name or name or '#%s' % picking.id

    @api.model
    def _return_e4_is_picking_name_collision_error(self, exc):
        err = str(exc).lower()
        return any(
            marker in err
            for marker in (
                'stock_picking_name_uniq',
                'duplicate key',
                'unique constraint',
                'referencia debe ser única',
                'reference must be unique',
            )
        )

    @api.model
    def _return_e4_reserve_unique_picking_name(self, picking_type, company=None):
        """
        Reserva un nombre de albarán único por empresa.
        Usa la secuencia del tipo; si no hay o está desincronizada, genera E4/CLS/…
        (evita el error «La referencia debe ser única por empresa» con nombre «/»).
        """
        Picking = self.env['stock.picking'].sudo()
        company = company or self.env.company
        company_id = company.id if company else self.env.company.id

        if picking_type and picking_type.sequence_id:
            for _attempt in range(30):
                candidate = picking_type.sequence_id.next_by_id()
                if (
                    candidate
                    and not self._return_e4_picking_name_looks_weak(candidate)
                    and not Picking.search_count([
                        ('name', '=', candidate),
                        ('company_id', '=', company_id),
                    ])
                ):
                    return candidate

        wh_code = 'WH'
        if picking_type and picking_type.warehouse_id:
            wh_code = (picking_type.warehouse_id.code or 'WH').replace(' ', '')
        stamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S')
        for _attempt in range(30):
            candidate = 'E4/CLS/%s/%s-%s' % (
                wh_code,
                stamp,
                uuid.uuid4().hex[:8].upper(),
            )
            if not Picking.search_count([
                ('name', '=', candidate),
                ('company_id', '=', company_id),
            ]):
                return candidate
        return 'E4/CLS/%s' % uuid.uuid4().hex.upper()

    def _return_e4_ensure_unique_picking_name(self):
        """Garantiza name único antes de confirmar/validar traslados de clasificación."""
        self.ensure_one()
        picking = self.sudo()
        company_id = picking.company_id.id or self.env.company.id
        if (
            picking.name
            and not self._return_e4_picking_name_is_placeholder(picking.name)
            and not self._return_e4_picking_name_looks_weak(picking.name)
            and not self.env['stock.picking'].sudo().search_count([
                ('name', '=', picking.name),
                ('company_id', '=', company_id),
                ('id', '!=', picking.id),
            ])
        ):
            return picking.name
        name = self._return_e4_reserve_unique_picking_name(
            picking.picking_type_id,
            picking.company_id,
        )
        picking.write({'name': name})
        return name

    def _return_e4_create_classification_picking(self, picking_type, vals):
        """Crea albarán de clasificación E4 con nombre único garantizado."""
        Picking = self.env['stock.picking'].sudo()
        company = picking_type.company_id or self.env.company
        base_vals = dict(vals)
        last_error = None
        for attempt in range(12):
            create_vals = dict(base_vals)
            create_vals['name'] = self._return_e4_reserve_unique_picking_name(
                picking_type, company,
            )
            try:
                return Picking.create(create_vals)
            except Exception as exc:
                last_error = exc
                if not self._return_e4_is_picking_name_collision_error(exc):
                    raise
                _logger.warning(
                    'E4 clasificación: colisión de nombre al crear (intento %s): %s',
                    attempt + 1, exc,
                )
        raise UserError(_(
            'No se pudo crear el traslado interno de clasificación E4: no hay un '
            'nombre de albarán disponible para el tipo «%(type)s».\n'
            'Revise la secuencia en Inventario → Tipos de operación.\n%(detail)s'
        ) % {
            'type': picking_type.display_name if picking_type else _('(sin tipo)'),
            'detail': last_error or '',
        })

    def action_confirm(self):
        for picking in self.filtered('invdash_is_return_e4_classification'):
            picking._return_e4_ensure_unique_picking_name()
        return super().action_confirm()

    def _return_e4_invalidate_route_move_cache(self, moves=None):
        """Evita referencias huérfanas a stock.move.line tras cancelar/liberar seriales."""
        self.ensure_one()
        self.invalidate_recordset(['move_line_ids', 'move_ids', 'state'])
        if moves:
            moves.invalidate_recordset(['move_line_ids', 'state', 'product_uom_qty', 'quantity'])

    def _return_e4_cancel_route_move_for_lots(self, move, lot_ids):
        """Cancela el movimiento o libera solo los seriales indicados (sin borrar líneas)."""
        if move.state in ('done', 'cancel'):
            return False
        active_lines = move.move_line_ids.filtered(
            lambda ml: ml.state not in ('done', 'cancel') and ml.lot_id,
        )
        target_lines = active_lines.filtered(lambda ml: ml.lot_id.id in lot_ids)
        if not target_lines:
            return False
        if len(target_lines) == len(active_lines):
            move._action_cancel()
            return True
        zero_vals = {'quantity': 0, 'picked': False}
        if 'qty_done' in target_lines._fields:
            zero_vals['qty_done'] = 0
        target_lines.write(zero_vals)
        remaining = active_lines - target_lines
        total = sum(remaining.mapped('quantity'))
        move_vals = {'product_uom_qty': total, 'picked': bool(remaining)}
        if 'quantity' in move._fields:
            move_vals['quantity'] = total
        move.write(move_vals)
        return False

    def _return_e4_release_route_lots_for_transfer(self, lots):
        """
        Libera en el E4 de ruta solo los seriales que se van a clasificar.
        Cancela movimientos en lugar de borrar líneas (evita stock.move.line huérfanas).
        """
        self.ensure_one()
        if not lots:
            return self.env['stock.move']
        lot_ids = set(lots.ids)
        MoveLine = self.env['stock.move.line'].sudo()
        lines = MoveLine.search([
            ('picking_id', '=', self.id),
            ('lot_id', 'in', list(lot_ids)),
            ('state', 'not in', ('done', 'cancel')),
        ])
        affected_moves = lines.move_id
        cancelled_moves = self.env['stock.move']
        for move in affected_moves.filtered(lambda m: m.state not in ('done', 'cancel')):
            try:
                if self._return_e4_cancel_route_move_for_lots(move, lot_ids):
                    cancelled_moves |= move
            except Exception as exc:
                _logger.info(
                    'E4: liberar movimiento de ruta pre-traslado (%s): %s',
                    move.display_name, exc,
                )
        if cancelled_moves:
            child_moves = self.move_ids.filtered(
                lambda m: m.internal_parent_move_id in cancelled_moves
                and m.state not in ('done', 'cancel')
            )
            for child in child_moves:
                try:
                    child._action_cancel()
                except Exception as exc:
                    _logger.info(
                        'E4: cancelar movimiento hijo pre-traslado (%s): %s',
                        child.display_name, exc,
                    )
        self._return_e4_invalidate_route_move_cache(affected_moves | cancelled_moves)
        return affected_moves

    def _return_e4_finalize_route_after_partial_transfer(self, lots, affected_moves):
        """Deja el E4 de ruta en Listo si quedan equipos pendientes."""
        self.ensure_one()
        if self.state in ('done', 'cancel') or not lots:
            return
        self._return_e4_invalidate_route_move_cache(affected_moves)
        self._return_e4_restore_route_assignment()

    def _return_e4_restore_route_assignment(self):
        """Reasigna el E4 de ruta para mantener Listo en traslados parciales."""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            return
        open_moves = self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        if not open_moves:
            return
        try:
            self.action_assign()
        except Exception as exc:
            _logger.info(
                'E4: reasignar albarán de ruta %s (%s)',
                self.display_name, exc,
            )
        self.invalidate_recordset(['state'])

    def _return_e4_supply_kind_for_line(self, line):
        """Clasificación supplies del movimiento según rol y línea de suministro."""
        if line.line_role in ('standalone', 'principal'):
            return 'parent'
        if not line.principal_lot or not line.lot:
            return 'component'
        SupplyLine = self.env['stock.lot.supply.line']
        supply_line = SupplyLine.search([
            ('lot_id', '=', line.principal_lot.id),
            ('related_lot_id', '=', line.lot.id),
        ], limit=1)
        if supply_line:
            kind_map = {
                'component': 'component',
                'peripheral': 'peripheral',
                'complement': 'complement',
                'monitor': 'monitor',
                'ups': 'ups',
            }
            return kind_map.get(supply_line.item_type, 'component')
        return 'component'

    def _return_e4_create_classification_moves(self, internal, lines, src_loc, dest_loc):
        """
        Crea movimientos padre/hijo para que asociados aparezcan en PRODUCTO PRINCIPAL.
        Si el principal va a otro destino, usa una fila ancla (sin mover su stock).
        """
        Move = self.env['stock.move']
        lines = list(lines)
        principals = [line for line in lines if line.line_role == 'principal' and line.lot]
        standalones = [line for line in lines if line.line_role == 'standalone' and line.lot]
        children = [
            line for line in lines
            if line.line_role in ('associated', 'bundled')
            and line.principal_lot
            and line.lot
        ]
        principal_lot_ids = {line.lot.id for line in principals}
        children_by_principal = {}
        for child in children:
            children_by_principal.setdefault(child.principal_lot.id, []).append(child)

        lot_move_map = {}

        def _move_vals(line, supply_kind, parent_move=False, extra=None):
            product = line.product or line.lot.product_id
            vals = {
                'description_picking': product.display_name,
                'picking_id': internal.id,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': line.quantity or 1.0,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'supply_kind': supply_kind,
            }
            if parent_move:
                vals['internal_parent_move_id'] = parent_move.id
            if extra:
                vals.update(extra)
            return vals

        def _register_move(line, move):
            if line.lot:
                lot_move_map[line.lot.id] = move

        for line in standalones:
            move = Move.create(_move_vals(line, 'parent'))
            _register_move(line, move)

        for line in principals:
            parent_move = Move.create(_move_vals(line, 'parent'))
            _register_move(line, parent_move)
            for child_line in children_by_principal.get(line.lot.id, []):
                child_move = Move.create(_move_vals(
                    child_line,
                    self._return_e4_supply_kind_for_line(child_line),
                    parent_move=parent_move,
                ))
                _register_move(child_line, child_move)

        for principal_lot_id, child_lines in children_by_principal.items():
            if principal_lot_id in principal_lot_ids:
                continue
            # Principal en otro destino/albarán: solo mover los asociados de este lote.
            for child_line in child_lines:
                move = Move.create(_move_vals(child_line, 'parent'))
                _register_move(child_line, move)

        return lot_move_map

    def _return_e4_finalize_anchor_classification_moves(self, internal):
        """Cierra filas ancla sin mover stock; solo referencia visual del principal."""
        anchor_moves = internal.move_ids.filtered('invdash_return_e4_anchor_only')
        if not anchor_moves:
            return
        MoveLine = self.env['stock.move.line']
        for move in anchor_moves:
            lot = move.invdash_return_e4_principal_lot_id
            if not lot:
                continue
            existing = move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
            if not existing:
                MoveLine.create({
                    'move_id': move.id,
                    'picking_id': internal.id,
                    'product_id': lot.product_id.id,
                    'product_uom_id': lot.product_id.uom_id.id,
                    'lot_id': lot.id,
                    'quantity': 0.0,
                    'picked': False,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                })
        anchor_moves.with_context(invdash_return_e4_admin_close=True)._action_done()

    def _return_e4_move_for_classification_entry(self, internal, moves, entry):
        """Movimiento destino de una línea (Odoo puede fusionar moves del mismo producto al confirmar)."""
        lot = entry.lot
        product = entry.product or lot.product_id
        lot_move_map = self.env.context.get('invdash_return_e4_lot_move_map') or {}
        if lot and lot.id in lot_move_map:
            return lot_move_map[lot.id]
        Move = self.env['stock.move']
        candidates = moves.filtered(
            lambda m: m.product_id == product and m.state not in ('done', 'cancel')
        )
        for move in candidates:
            if not move.move_line_ids.filtered(lambda ml: ml.lot_id == lot):
                return move
        if candidates:
            return candidates[0]
        return Move.create({
            'description_picking': product.display_name,
            'picking_id': internal.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': entry.quantity or 1.0,
            'location_id': internal.location_id.id,
            'location_dest_id': internal.location_dest_id.id,
            'supply_kind': self._return_e4_supply_kind_for_line(entry),
        })

    def _return_e4_apply_classification_move_line(self, internal, move, entry):
        """Crea o actualiza la línea detalle con el serial indicado."""
        if move.invdash_return_e4_anchor_only:
            return
        MoveLine = self.env['stock.move.line']
        qty = entry.quantity or 1.0
        lot = entry.lot
        product = entry.product or lot.product_id
        existing = move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
        ml_vals = {
            'quantity': qty,
            'picked': True,
            'lot_id': lot.id,
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
        }
        if 'qty_done' in MoveLine._fields:
            ml_vals['qty_done'] = qty
        if existing:
            existing.write(ml_vals)
        else:
            ml_vals.update({
                'move_id': move.id,
                'picking_id': internal.id,
            })
            MoveLine.create(ml_vals)

    def _return_e4_sync_classification_move_quantities(self, internal):
        """Sincroniza demanda de cada movimiento con sus seriales asignados."""
        for move in internal.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            lines = move.move_line_ids.filtered(lambda ml: ml.lot_id and ml.quantity)
            if not lines:
                continue
            total = sum(lines.mapped('quantity'))
            vals = {'product_uom_qty': total, 'picked': True}
            if 'quantity' in move._fields:
                vals['quantity'] = total
            move.write(vals)

    def _return_e4_should_auto_validate_classification(self, line_entries):
        """Solo Existencias se valida al ejecutar traslados; el resto queda en Listo."""
        destinations = {
            entry.destination
            for entry in line_entries
            if entry.lot and entry.destination
        }
        return destinations == {'stock'}

    def _validate_return_e4_classification_picking(self, internal, line_entries):
        """Prepara traslado interno; valida solo si el destino es Existencias."""
        self.ensure_one()
        line_entries = list(line_entries)
        auto_validate = self._return_e4_should_auto_validate_classification(line_entries)
        internal._return_e4_ensure_unique_picking_name()
        if internal.state == 'draft':
            try:
                internal.action_confirm()
            except Exception as exc:
                if self._return_e4_is_picking_name_collision_error(exc):
                    internal._return_e4_ensure_unique_picking_name()
                    internal.action_confirm()
                else:
                    raise
            internal._return_e4_ensure_unique_picking_name()

        moves = internal.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        missing_lots = []
        for entry in line_entries:
            if not entry.lot:
                continue
            move = self._return_e4_move_for_classification_entry(internal, moves, entry)
            if move.invdash_return_e4_anchor_only:
                continue
            moves |= move
            self._return_e4_apply_classification_move_line(internal, move, entry)

        self._return_e4_sync_classification_move_quantities(internal)
        self._return_e4_finalize_anchor_classification_moves(internal)

        moves = internal.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        for entry in line_entries:
            if not entry.lot:
                continue
            found = moves.filtered(
                lambda m: not m.invdash_return_e4_anchor_only
                and m.move_line_ids.filtered(lambda ml: ml.lot_id == entry.lot)
            )
            if not found:
                missing_lots.append(entry.lot.display_name)
        if missing_lots:
            raise UserError(_(
                'No se pudo asignar el serial en el traslado %(name)s:\n%s'
            ) % {
                'name': internal.display_name or internal.name,
                'lines': '\n'.join(missing_lots[:15]),
            })

        if internal.state == 'confirmed':
            try:
                internal.action_assign()
                for entry in line_entries:
                    if not entry.lot:
                        continue
                    qty = entry.quantity or 1.0
                    for ml in internal.move_line_ids.filtered(
                        lambda m: m.lot_id == entry.lot
                    ):
                        ml.write({'quantity': qty, 'picked': True})
                self._return_e4_sync_classification_move_quantities(internal)
            except Exception as exc:
                _logger.info('Clasificación E4: action_assign (%s)', exc)

        if not auto_validate:
            return internal

        res = internal.with_context(
            skip_immediate=True,
            skip_backorder=True,
            cancel_backorder=True,
            invdash_return_e4_classification=True,
        ).button_validate()

        if isinstance(res, dict) and res.get('res_model') and res.get('res_id'):
            model = res['res_model']
            ctx = dict(self.env.context)
            ctx.update(res.get('context') or {})
            wiz = self.env[model].with_context(ctx).browse(res['res_id'])
            if model == 'stock.immediate.transfer':
                for method in ('process', 'action_process'):
                    if hasattr(wiz, method):
                        getattr(wiz, method)()
                        break
            elif model == 'stock.backorder.confirmation':
                for method in ('process_cancel_backorder', 'process', 'action_process'):
                    if hasattr(wiz, method):
                        getattr(wiz, method)()
                        break
            internal.invalidate_recordset(['state'])

        if internal.state != 'done':
            pending = internal.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
            )
            try:
                for move in pending:
                    if 'quantity' in move._fields:
                        move.write({'quantity': move.product_uom_qty, 'picked': True})
                if pending:
                    pending._action_done()
                internal.invalidate_recordset(['state'])
            except Exception as exc:
                _logger.warning('Clasificación E4: _action_done directo falló: %s', exc)

        if internal.state != 'done':
            details = []
            Quant = self.env['stock.quant'].sudo()
            for move in internal.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                lot = move.move_line_ids[:1].lot_id
                loc_name = _('sin stock interno')
                if lot:
                    q = Quant.search([
                        ('lot_id', '=', lot.id),
                        ('quantity', '>', 0),
                    ], limit=1)
                    if q:
                        loc_name = q.location_id.complete_name
                label = lot.name if lot else move.product_id.display_name
                details.append('%s → %s' % (label, loc_name))
            raise UserError(_(
                'No se pudo validar el traslado %(src)s → %(dest)s (%(name)s).\n'
                'Valide E3 (Devolución → Verificación) o revise ubicación actual:\n%(lines)s'
            ) % {
                'src': internal.location_id.display_name,
                'dest': internal.location_dest_id.display_name,
                'name': internal.display_name or internal.name,
                'lines': '\n'.join(details[:12]) or _('(sin detalle)'),
            })
        return internal

    @api.model
    def _return_e4_destination_label(self, destination_code):
        return RETURN_E4_DESTINATION_LABELS.get(destination_code, destination_code or '')

    @api.model
    def _return_e4_disassociation_chatter_body(self, items):
        """
        items: list of (principal_name, associated_name, destination_code)
        """
        if not items:
            return Markup('')
        lines = []
        for principal, assoc, dest_code in items[:20]:
            dest_label = self._return_e4_destination_label(dest_code)
            lines.append(
                Markup('• %s → %s a <strong>%s</strong>') % (
                    Markup.escape(principal or ''),
                    Markup.escape(assoc or ''),
                    Markup.escape(dest_label),
                )
            )
        return Markup(
            '<p>E4: Se desasociaron elementos por destino diferente al principal:</p>'
            '<p>%s</p>'
        ) % Markup('<br/>'.join(lines))

    def _return_e4_disassociate_supply_line(self, principal_lot, associated_lot):
        """Quita la asociación principal→asociado (evita re-autollenado en product_suppiles)."""
        self.ensure_one()
        if not principal_lot or not associated_lot:
            return False
        SupplyLine = self.env['stock.lot.supply.line'].sudo()
        links = SupplyLine.search([
            ('lot_id', '=', principal_lot.id),
            ('related_lot_id', '=', associated_lot.id),
        ])
        if not links:
            return False
        principals = links.mapped('lot_id')
        to_unlink = links.filtered(
            lambda sl: sl.item_type in ('complement', 'peripheral') and not sl.has_cost
        )
        to_clear = links - to_unlink
        if to_unlink:
            to_unlink.unlink()
        if to_clear:
            to_clear.with_context(invdash_skip_supply_autofill=True).write({
                'related_lot_id': False,
            })
        principals.invalidate_recordset([
            'lot_supply_line_ids',
            'lot_supply_line_sin_costo_ids',
            'lot_supply_line_con_costo_ids',
        ])
        return True

    def _archive_return_e4_classification_lines(self, processing_lines):
        """Añade al archivo E4 los seriales recién trasladados (clasificación parcial)."""
        self.ensure_one()
        Classified = self.env['stock.picking.return.e4.classified.line'].sudo()
        existing_lots = set(self.invdash_return_e4_classified_line_ids.mapped('lot_id').ids)
        vals_list = []
        for pl in processing_lines:
            if not pl.lot or pl.lot.id in existing_lots:
                continue
            existing_lots.add(pl.lot.id)
            principal_lot_id = False
            if pl.principal_lot:
                principal_lot_id = pl.principal_lot.id
            elif pl.line_role == 'principal' and pl.lot:
                principal_lot_id = pl.lot.id
            vals_list.append({
                'picking_id': self.id,
                'line_role': pl.line_role,
                'principal_lot_id': principal_lot_id,
                'lot_id': pl.lot.id,
                'quantity': pl.quantity,
                'destination': pl.destination,
            })
        if vals_list:
            Classified.create(vals_list)

    def _return_e4_force_done_administrative(self):
        """Marca el E4 de ruta como hecho sin volver a mover inventario."""
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        if not moves:
            return True
        ctx = {
            'invdash_return_e4_admin_close': True,
            'mail_notrack': True,
            'skip_sanity_check': True,
            'cancel_backorder': True,
        }
        try:
            moves.with_context(**ctx)._action_done()
        except Exception as exc:
            _logger.warning(
                'E4 devolución: cierre administrativo falló en %s: %s',
                self.display_name, exc,
            )
            moves.with_context(**ctx).write({'state': 'done'})
        self.invalidate_recordset(['state'])
        return True

    def _complete_return_e4_route_picking_after_classification(self):
        """Cierra el E4 de ruta en Hecho; el stock ya salió por traslados de clasificación."""
        self.ensure_one()
        if self.state == 'done':
            return True
        return self._return_e4_force_done_administrative()

    def _return_route_e4_pre_validate_action(self):
        """Si falta dictamen/traslado E4, abre el wizard o bloquea validación manual."""
        if self.env.context.get('invdash_return_e4_skip_stock'):
            return None

        e4_pickings = self.filtered(
            lambda p: p._is_return_route_e4_picking()
            and p.state not in ('done', 'cancel')
        )
        if not e4_pickings:
            return None

        for picking in e4_pickings:
            picking._return_e4_sync_dictamen_lines()

        partial = e4_pickings.filtered(
            lambda p: p.invdash_return_e4_dictamen_line_ids
            and not p.invdash_return_e4_all_dictamen_done
            and p.invdash_return_e4_dictamen_line_ids.filtered(
                lambda l: l.state != 'unassigned'
            )
        )
        if partial:
            if len(partial) == 1:
                raise UserError(_(
                    'La verificación E4 está en curso (%s). '
                    'Complete asignación, verificación y traslados de todos los equipos '
                    'desde «Asignación Técnicos» antes de validar manualmente.'
                ) % (partial.invdash_return_e4_dictamen_progress or ''))
            raise UserError(_(
                'Hay albaranes E4 con verificación incompleta. Use «Asignación Técnicos».'
            ))

        need = e4_pickings.filtered(lambda p: not p.invdash_return_e4_all_dictamen_done)
        if not need:
            return None
        if len(need) == 1:
            return need.action_open_return_e4_classification_wizard()
        names = ', '.join(need.mapped('display_name')[:5])
        raise UserError(_(
            'Debe completar la verificación E4 antes de validar estos albaranes de devolución:\n%s'
        ) % names)
