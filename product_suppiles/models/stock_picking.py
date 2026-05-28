# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_datetime
import logging
import re

try:
    from lxml import etree
except ImportError:
    etree = None

_logger = logging.getLogger(__name__)


def _arch_to_etree(arch):
    """Convierte arch de vista (etree, str o bytes) en elemento raíz lxml."""
    if etree is None or arch is None:
        return None
    try:
        if hasattr(arch, 'tag'):
            return arch
        if isinstance(arch, bytes):
            arch_str = arch.decode('utf-8')
        elif isinstance(arch, str):
            arch_str = arch
        else:
            return None
        if arch_str.strip().startswith('<?xml'):
            arch_str = arch_str.split('?>', 1)[-1].strip()
        return etree.fromstring(arch_str.encode('utf-8'))
    except Exception:
        _logger.exception("[product_suppiles] _arch_to_etree: error parseando arch")
        return None


def _is_truthy_invisible_xml(node):
    inv = (node.get('invisible') or '').strip().lower()
    return inv in ('1', 'true', '1.0')


def _is_field_inside_subview_list_or_tree(node):
    """True si el field está dentro de un <tree>/<list> (ej. columnas de movimientos), no en la cabecera."""
    if node is None:
        return False
    return bool(node.xpath("ancestor::*[local-name()='tree' or local-name()='list']"))


def _rewrite_scheduled_date_o_row_wrap(root):
    """
    Sustituye el div.o_row del estándar Stock por un contenedor con min-width estable.
    Así la vista fusionada (Studio) también queda corregida aunque el xpath XML no coincida.
    """
    if etree is None:
        return
    for fld in list(root.xpath("//field[@name='scheduled_date']")):
        if _is_field_inside_subview_list_or_tree(fld):
            continue
        if fld.xpath("ancestor::div[contains(@class,'o_supplies_scheduled_date_wrap')]"):
            continue
        o_row_div = None
        node = fld.getparent()
        while node is not None:
            cls = node.get('class') or ''
            if 'o_row' in cls:
                o_row_div = node
                break
            node = node.getparent()
        if o_row_div is None:
            continue
        parent = o_row_div.getparent()
        if parent is None:
            continue
        idx = parent.index(o_row_div)
        o_row_div.remove(fld)
        parent.remove(o_row_div)
        wrap = etree.Element('div')
        wrap.set(
            'class',
            'o_supplies_scheduled_date_wrap d-flex flex-row flex-nowrap align-items-center w-100',
        )
        cls_f = (fld.get('class') or '').strip()
        for part in ('o_supplies_scheduled_date_single_line', 'flex-grow-1', 'flex-shrink-0'):
            parts = cls_f.split()
            if part not in parts:
                parts.append(part)
                cls_f = ' '.join(parts)
        fld.set('class', cls_f)
        wrap.append(fld)
        parent.insert(idx, wrap)


def _normalize_picking_form_scheduled_date_arch(arch):
    """
    Vista fusionada (incl. Studio):
    - Quita supplies_scheduled_date_display (legacy).
    - En cabecera del form: elimina date_deadline y json_popover (replanificación Odoo), que duplican fechas
      y el deadline suele verse en rojo con valor distinto a scheduled_date.
    - No toca date_deadline dentro de subvistas list/tree (operaciones).
    - Dedup de scheduled_date si Studio duplicó el campo.
    """
    root = _arch_to_etree(arch)
    if root is None:
        return arch
    try:
        for lbl in root.xpath("//label[@for='supplies_scheduled_date_display']"):
            lbl.set('for', 'scheduled_date')

        for node in list(root.xpath("//field[@name='supplies_scheduled_date_display']")):
            p = node.getparent()
            if p is not None:
                p.remove(node)

        for fname in ('date_deadline', 'json_popover'):
            for node in list(root.xpath("//field[@name='%s']" % fname)):
                if _is_field_inside_subview_list_or_tree(node):
                    continue
                p = node.getparent()
                if p is not None:
                    p.remove(node)

        _rewrite_scheduled_date_o_row_wrap(root)

        sched_nodes = list(root.xpath("//field[@name='scheduled_date']"))
        if len(sched_nodes) > 1:
            visible = [n for n in sched_nodes if not _is_truthy_invisible_xml(n)]
            keep = visible[0] if visible else sched_nodes[0]
            for n in sched_nodes:
                if n is keep:
                    continue
                if n.get('required') and not keep.get('required'):
                    keep.set('required', n.get('required'))
                p = n.getparent()
                if p is not None:
                    p.remove(n)

        # Clase para CSS: evita que la celda flex encoja el datetime hasta partir el texto en vertical.
        for node in root.xpath("//field[@name='scheduled_date']"):
            if _is_field_inside_subview_list_or_tree(node):
                continue
            cls = (node.get('class') or '').strip()
            mark = 'o_supplies_scheduled_date_single_line'
            parts = cls.split()
            if mark not in parts:
                parts.append(mark)
                node.set('class', ' '.join(parts))
    except Exception:
        _logger.exception("[product_suppiles] _normalize_picking_form_scheduled_date_arch falló")
        return arch
    return root


# XML de la pestaña "Productos principales" para inyectar en el form de picking (fallback si la herencia XML no aplica).
PICKING_SUPPLIES_PAGE_XML = """<page name="supplies_main_only" string="Productos principales" class="supplies-main-products-page">
  <group string="Producto Principal" class="supplies-main-products-group">
    <group col="2">
      <button name="action_detailed_operations" type="object" string="Cambiar seriales" class="btn-secondary"/>
    </group>
    <field name="move_line_ids_main_only" nolabel="1">
      <list create="0" delete="0" decoration-muted="supply_kind != 'parent'" editable="false" class="o_supplies_main_products_list">
        <field name="product_display_clean" string="Producto"/>
        <field name="supply_kind" column_invisible="1"/>
        <field name="lot_id" string="Número de Serie" readonly="1" optional="show" invisible="supply_kind != 'parent' or not lot_id" options="{'no_create': True}"/>
        <field name="associated_components" string="Componentes" readonly="1" optional="show" invisible="supply_kind != 'parent'" widget="text"/>
        <field name="associated_peripherals" string="Periféricos" readonly="1" optional="show" invisible="supply_kind != 'parent'" widget="text"/>
        <field name="associated_complements" string="Complementos" readonly="1" optional="show" invisible="supply_kind != 'parent'" widget="text"/>
        <field name="associated_licenses" string="Licencias" readonly="1" optional="show" invisible="supply_kind != 'parent'" widget="text"/>
        <button name="action_open_lot_wizard" type="object" string="Editar" invisible="supply_kind != 'parent' or not lot_id or picking_id.state == 'done'" class="btn-link" title="Editar elementos asociados del lote"/>
        <field name="quantity" string="Demanda"/>
      </list>
    </field>
  </group>
</page>"""

PICKING_OBSERVACION_LI_PAGE_XML = """<page name="observacion_li" string="Observación L&amp;I">
  <group col="1">
    <div class="alert alert-info" role="alert">
      <strong>Uso exclusivo de Logística e Inventario:</strong>
      la información registrada en esta pestaña se usará como observación en el acta de recepción o devolución de activos.
    </div>
    <field name="observation_li" nolabel="1" placeholder="Escribe aquí la observación..." readonly="state in ['done', 'cancel']"/>
  </group>
</page>"""


def _inject_picking_supplies_page(arch):
    """Inyecta pestañas custom en el form de stock.picking. Devuelve elemento etree (no string)."""
    if etree is None:
        return arch
    try:
        if hasattr(arch, 'tag'):
            # arch ya es un elemento etree: usarlo y modificar in-place
            root = arch
        elif isinstance(arch, bytes):
            arch_str = arch.decode('utf-8')
            if arch_str.strip().startswith('<?xml'):
                arch_str = arch_str.split('?>', 1)[-1].strip()
            root = etree.fromstring(arch_str.encode('utf-8'))
        elif isinstance(arch, str):
            arch_str = arch
            if arch_str.strip().startswith('<?xml'):
                arch_str = arch_str.split('?>', 1)[-1].strip()
            root = etree.fromstring(arch_str.encode('utf-8'))
        else:
            return arch
        notebooks = root.xpath('//notebook') or root.xpath('//*[local-name()="notebook"]')
        if not notebooks:
            _logger.warning("[product_suppiles] stock.picking form: no se encontró <notebook>, no se inyecta pestaña")
            return arch
        nb = notebooks[0]
        existing = nb.xpath("./page[@name='supplies_main_only']")
        if existing:
            page_el = existing[0]
            nb.remove(page_el)
            nb.insert(0, page_el)
        else:
            page_node = etree.fromstring(PICKING_SUPPLIES_PAGE_XML)
            nb.insert(0, page_node)

        existing_obs = nb.xpath("./page[@name='observacion_li']")
        if not existing_obs:
            obs_node = etree.fromstring(PICKING_OBSERVACION_LI_PAGE_XML)
            note_page = nb.xpath("./page[@name='note']")
            if note_page:
                note_idx = nb.index(note_page[0])
                nb.insert(note_idx + 1, obs_node)
            else:
                nb.append(obs_node)
        # Importante: devolver el elemento, no string (ir.ui.view espera .tag)
        return root
    except Exception as e:
        _logger.exception("[product_suppiles] stock.picking form: error inyectando pestaña Productos principales: %s", e)
        return arch


def _run_consolidation_loop(picking, max_iter=10):
    """Ejecuta consolidación en bucle hasta que no se elimine ninguna línea. Retorna total eliminado."""
    total = 0
    for _ in range(max_iter):
        removed = picking.env["stock.move.line"]._consolidate_duplicate_move_lines_for_picking(picking)
        total += removed
        if removed == 0:
            break
    return total

class StockPicking(models.Model):
    _inherit = "stock.picking"

    observation_li = fields.Text(
        string="Observación L&I",
        tracking=True,
        help="Observaciones internas para el proceso L&I del traslado.",
    )

    def _supplies_snapshot_picking_serials(self):
        """Copia de seriales reservados antes de write que pueda desasignar líneas."""
        snapshot = {}
        for picking in self:
            lines = picking.move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.quantity and ml.product_id.tracking == 'serial'
            )
            if not lines:
                continue
            snapshot[picking.id] = [{
                'move_id': ml.move_id.id,
                'product_id': ml.product_id.id,
                'lot_id': ml.lot_id.id,
                'quantity': ml.quantity,
                'location_id': ml.location_id.id,
                'location_dest_id': ml.location_dest_id.id,
                'product_uom_id': ml.product_uom_id.id,
            } for ml in lines]
        return snapshot

    def _supplies_restore_picking_serials(self, snapshot):
        if not snapshot:
            return
        MoveLine = self.env['stock.move.line']
        for picking in self:
            items = snapshot.get(picking.id)
            if not items:
                continue
            for item in items:
                if picking.move_line_ids.filtered(
                    lambda ml: ml.lot_id.id == item['lot_id'] and ml.quantity
                ):
                    continue
                move = self.env['stock.move'].browse(item['move_id'])
                if not move.exists():
                    continue
                MoveLine.create({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': item['product_id'],
                    'lot_id': item['lot_id'],
                    'quantity': item['quantity'],
                    'picked': True,
                    'location_id': item['location_id'],
                    'location_dest_id': item['location_dest_id'],
                    'product_uom_id': item['product_uom_id'],
                })

    @staticmethod
    def _route_stage_from_origin(origin):
        """Etapa E# del wizard de rutas (Ruta-...-E3 o Ruta: ... W1 - E3)."""
        if not origin:
            return 0
        text = (origin or '').strip()
        match = re.search(r'-E(\d+)\s*$', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r'[\s-]E(\d+)\s*$', text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _is_route_wizard_origin(origin):
        if not origin:
            return False
        text = (origin or '').strip()
        low = text.lower()
        if not (low.startswith('ruta-') or low.startswith('ruta:')):
            return False
        return bool(re.search(r'[\s-]e\d+\s*$', text, re.IGNORECASE))

    @staticmethod
    def _route_wave_id_from_origin(origin):
        if not origin:
            return ''
        match = re.search(r'W(\d+)', origin, re.IGNORECASE)
        return match.group(1) if match else ''

    def _route_origin_base(self):
        self.ensure_one()
        origin = (self.origin or '').strip()
        if not self._is_route_wizard_origin(origin):
            return ''
        if origin.startswith('Ruta-') and '-E' in origin:
            return origin.rsplit('-E', 1)[0]
        wave = self._route_wave_id_from_origin(origin)
        if wave:
            return 'W%s' % wave
        return origin

    def _get_route_chain_pickings(self):
        self.ensure_one()
        origin = (self.origin or '').strip()
        if not self._is_route_wizard_origin(origin):
            return self.env['stock.picking']
        wave = self._route_wave_id_from_origin(origin)
        if wave and self.partner_id:
            chain = self.search([
                ('partner_id', '=', self.partner_id.id),
                ('origin', 'ilike', 'W%s' % wave),
            ])
            return chain.filtered(lambda p: self._is_route_wizard_origin(p.origin))
        base = self._route_origin_base()
        if not base:
            return self.env['stock.picking']
        if base.startswith('W') and self.partner_id:
            return self.search([
                ('partner_id', '=', self.partner_id.id),
                ('origin', 'ilike', base),
            ]).filtered(lambda p: self._is_route_wizard_origin(p.origin))
        return self.search([
            ('origin', '=like', base + '-E%'),
        ]) | self.search([
            ('origin', 'ilike', base),
            ('origin', 'ilike', '%E%'),
        ])

    def _get_parent_moves_for_route(self):
        self.ensure_one()
        return self.move_ids.filtered(
            lambda m: not m.internal_parent_move_id
            and (not getattr(m, 'supply_kind', False) or m.supply_kind == 'parent')
        )

    def _sync_route_chain_from_picking(self):
        """Si se agregan productos después del wizard, replicarlos en etapas E2, E3… de la ruta."""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            return

        chain = self._get_route_chain_pickings().filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        if len(chain) < 2:
            return

        stages = sorted(chain, key=lambda p: self._route_stage_from_origin(p.origin))
        start_idx = next((i for i, p in enumerate(stages) if p.id == self.id), None)
        if start_idx is None:
            return

        prev_moves = self._get_parent_moves_for_route()
        Move = self.env['stock.move']

        for picking in stages[start_idx + 1:]:
            next_prev_moves = Move
            for prev_move in prev_moves:
                existing = picking.move_ids.filtered(
                    lambda m: prev_move in m.move_orig_ids
                    or (
                        m.product_id == prev_move.product_id
                        and not m.internal_parent_move_id
                        and (not getattr(m, 'supply_kind', False) or m.supply_kind == 'parent')
                    )
                )
                if existing:
                    next_prev_moves |= existing
                    continue

                prev_desc = (
                    getattr(prev_move, 'description_picking', None)
                    or (prev_move.product_id.display_name if prev_move.product_id else '')
                )
                move_vals = {
                    'description_picking': prev_desc,
                    'product_id': prev_move.product_id.id,
                    'product_uom': prev_move.product_uom.id,
                    'product_uom_qty': prev_move.product_uom_qty,
                    'picking_id': picking.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'company_id': picking.company_id.id,
                    'move_orig_ids': [(4, prev_move.id)],
                }
                if getattr(prev_move, 'supply_kind', False):
                    move_vals['supply_kind'] = prev_move.supply_kind
                new_move = Move.create(move_vals)
                next_prev_moves |= new_move

            if picking.state == 'draft' and picking.move_ids:
                picking.action_confirm()
            prev_moves = next_prev_moves.filtered(
                lambda m: not getattr(m, 'supply_kind', False) or m.supply_kind == 'parent'
            )

    def _supplies_prepare_moves_for_validation(self):
        """
        Odoo 19 valida con move.quantity y move.picked.
        Sincroniza líneas con serial para evitar backorder falso y que solo pase la línea 1.
        """
        for picking in self:
            parents = picking.move_ids.filtered(
                lambda m: not m.internal_parent_move_id
                and (not getattr(m, 'supply_kind', False) or m.supply_kind == 'parent')
            )
            for move in parents:
                lines = move.move_line_ids.filtered(lambda ml: ml.quantity > 0)
                if not lines:
                    continue
                lines.write({'picked': True})
                rounding = move.product_uom.rounding
                if float_compare(move.quantity, move.product_uom_qty, precision_rounding=rounding) < 0:
                    move.quantity = move.product_uom_qty
                move.picked = True

            for child in picking.move_ids.filtered('internal_parent_move_id'):
                if child.internal_parent_move_id not in picking.move_ids:
                    continue
                clines = child.move_line_ids.filtered(lambda ml: ml.lot_id and ml.quantity > 0)
                if not clines:
                    continue
                clines.write({'picked': True})
                rounding = child.product_uom.rounding
                if float_compare(child.quantity, child.product_uom_qty, precision_rounding=rounding) < 0:
                    child.quantity = child.product_uom_qty
                child.picked = True

    def write(self, vals):
        if 'observation_li' in vals:
            locked = self.filtered(lambda p: p.state in ('done', 'cancel'))
            if locked:
                raise UserError(_("No se puede modificar la Observación L&I cuando la operación está en estado Hecho o Cancelado."))
        preserve_serials = (
            not self.env.context.get('skip_supplies_serial_preserve')
            and ('move_ids' in vals or 'move_ids_without_package' in vals or 'picking_type_id' in vals)
        )
        serial_snapshot = self._supplies_snapshot_picking_serials() if preserve_serials else {}
        sync_route_chain = 'move_ids' in vals or 'move_ids_without_package' in vals
        res = super().write(vals)
        if serial_snapshot:
            self._supplies_restore_picking_serials(serial_snapshot)
        if sync_route_chain and not self.env.context.get('skip_route_chain_sync'):
            for picking in self:
                if picking._route_origin_base():
                    picking._sync_route_chain_from_picking()
        return res

    # Campo computed para mostrar solo líneas principales
    move_ids_main_only = fields.One2many(
        'stock.move',
        'picking_id',
        string='Movimientos principales',
        compute='_compute_move_ids_main_only',
        store=False,
        help='Solo muestra movimientos con supply_kind = parent'
    )
    
    @api.depends('move_ids', 'move_ids.supply_kind', 'move_ids.internal_parent_move_id')
    def _compute_move_ids_main_only(self):
        """Mostrar movimientos principales sin perder líneas válidas por datos heredados."""
        for picking in self:
            try:
                # Odoo 19: la vista usa move_ids; el modelo puede tener move_ids_without_package (stock) o no
                moves = getattr(picking, 'move_ids_without_package', None) or picking.move_ids
                main_moves = moves.filtered(
                    lambda m: (
                        (not hasattr(m, 'internal_parent_move_id') or not m.internal_parent_move_id)
                        and (
                            (hasattr(m, 'supply_kind') and m.supply_kind == 'parent')
                            or (not hasattr(m, 'supply_kind') or not m.supply_kind)
                        )
                    )
                )
                # Fallback: si por datos previos no hay "parent", mostrar top-level para no ocultar productos.
                if not main_moves:
                    main_moves = moves.filtered(lambda m: not getattr(m, 'internal_parent_move_id', False))
                picking.move_ids_main_only = main_moves
            except Exception:
                picking.move_ids_main_only = self.env['stock.move']
    
    # Campo computed para mostrar solo move_line_ids principales en "Operaciones detalladas"
    move_line_ids_main_only = fields.One2many(
        'stock.move.line',
        'picking_id',
        string='Líneas principales',
        compute='_compute_move_line_ids_main_only',
        store=False,
        help='Solo muestra move_line_ids con supply_kind = parent'
    )
    
    @api.depends('move_line_ids', 'move_line_ids.supply_kind')
    def _compute_move_line_ids_main_only(self):
        """Odoo 19: usa move_line_ids. Solo líneas con supply_kind = 'parent'."""
        for picking in self:
            try:
                lines = getattr(picking, 'move_line_ids_without_package', None) or picking.move_line_ids
                picking.move_line_ids_main_only = lines.filtered(
                    lambda ml: hasattr(ml, 'supply_kind') and ml.supply_kind == 'parent'
                )
            except Exception:
                picking.move_line_ids_main_only = self.env['stock.move.line']

    def action_debug_date_render(self):
        self.ensure_one()
        dt = self.scheduled_date or self.date_deadline
        try:
            formatted = (
                format_datetime(
                    self.env,
                    dt,
                    tz=self.env.user.tz or "UTC",
                    dt_format="dd/MM/y HH:mm",
                    lang_code=self.env.lang or None,
                )
                if dt
                else "N/A"
            )
        except Exception:
            formatted = str(dt) if dt else "N/A"
        msg = _(
            "scheduled_date: %(scheduled)s\n"
            "date_deadline: %(deadline)s\n"
            "TZ usuario: %(tz)s\n"
            "Lang: %(lang)s\n"
            "format_datetime: %(formatted)s"
        ) % {
            'scheduled': self.scheduled_date or 'N/A',
            'deadline': self.date_deadline or 'N/A',
            'tz': self.env.user.tz or 'UTC',
            'lang': self.env.lang or 'N/A',
            'formatted': formatted,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug fecha programada'),
                'message': msg,
                'type': 'warning',
                'sticky': True,
            },
        }
    

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Inyecta la pestaña 'Productos principales' en el form para que funcione aunque la herencia XML no aplique."""
        try:
            result = super()._get_view(view_id=view_id, view_type=view_type, **options)
        except Exception as e:
            _logger.exception("[product_suppiles] stock.picking _get_view: error en super: %s", e)
            raise
        # Odoo puede devolver (arch, view) o un dict
        if isinstance(result, tuple) and len(result) >= 2:
            arch, view = result[0], result[1]
            if view_type == 'form':
                # Cabecera: una sola fecha útil (scheduled_date); quitar deadline/popover duplicados del arch fusionado.
                arch = _normalize_picking_form_scheduled_date_arch(arch)
                arch = _inject_picking_supplies_page(arch)
            return (arch, view)
        # Si devuelve otra cosa (ej. dict), no modificar
        return result

    def action_debug_consolidate_serial_lines(self):
        """
        Botón de depuración: ejecuta consolidación en bucle y muestra si quedan
        duplicados (producto + serie repetidos). Ayuda a diagnosticar el error
        "Este número de serie ya había sido asignado".
        """
        self.ensure_one()
        if not self.move_line_ids:
            raise UserError(_("Este traslado no tiene líneas de operación."))
        total_merged = _run_consolidation_loop(self)
        report = self.env["stock.move.line"]._get_duplicate_serial_report(self)
        if report:
            lines_msg = "\n".join(
                _("• Producto: %s | Serie: %s | Líneas repetidas: %s") % (prod, ser, cnt)
                for prod, ser, cnt in report
            )
            raise UserError(
                _("Consolidación ejecutada (%s líneas fusionadas).\n\n"
                  "Aún hay duplicados (mismo producto + mismo número de serie en varias líneas):\n\n%s\n\n"
                  "Estos productos/series provocan el error al validar. Revise por qué hay varias líneas "
                  "con el mismo serial (p. ej. componentes/periféricos repetidos).")
                % (total_merged, lines_msg)
            )
        raise UserError(
            _("Consolidación OK.\n\nSe fusionaron %s líneas duplicadas. No quedan duplicados (producto + serie).\n"
              "Puede intentar validar de nuevo.")
            % total_merged
        )

    def action_detailed_operations(self):
        """
        Sobrescribe el método estándar para filtrar solo productos principales
        en la vista de "Operaciones detalladas".
        """
        action = super().action_detailed_operations()
        if action and isinstance(action, dict):
            # Agregar dominio para mostrar solo productos principales
            domain = action.get('domain', [])
            if not any('supply_kind' in str(d) for d in domain):
                domain = domain + [('supply_kind', '=', 'parent')]
            action['domain'] = domain
        return action

    def button_validate(self):
        # Consolidar líneas duplicadas (mismo product_id+lot_id) ANTES de validar
        # para evitar "Este número de serie ya había sido asignado" (entrega/devolución).
        # Ejecutar en bucle hasta que no queden duplicados (máx 10 pasadas).
        for picking in self:
            if picking.exists() and picking.move_line_ids:
                for _ in range(10):
                    removed = self.env["stock.move.line"]._consolidate_duplicate_move_lines_for_picking(picking)
                    if removed == 0:
                        break
        for picking in self:
            picking._sync_route_chain_from_picking()
        self._supplies_prepare_moves_for_validation()
        # Validar el picking
        res = super().button_validate()
        self._log_supplies_purchase_history()
        # Cuando un equipo sale de la ubicación del cliente (devolución), marcar Fecha Finalizacion Renting
        try:
            self._set_renting_exit_date_on_return()
        except Exception as e:
            _logger.warning("Error al actualizar Fecha Finalizacion Renting en devoluciones: %s", str(e))
        # Cuando se ENTREGA de nuevo un equipo al cliente, limpiar fecha de salida para no mostrar la anterior
        try:
            self._clear_renting_dates_on_delivery_to_client()
        except Exception as e:
            _logger.warning("Error al limpiar fechas Renting en entregas al cliente: %s", str(e))
        
        # Después de validar, intentar confirmar pickings destino que estén en borrador
        try:
            for picking in self:
                if not picking or not picking.exists():
                    continue
                
                # Buscar movimientos que tienen move_dest_ids (siguiente etapa en la cadena)
                moves_with_dest = picking.move_ids.filtered(
                    lambda m: m.move_dest_ids and m.state == 'done'
                )
                
                if moves_with_dest:
                    # Para cada movimiento destino, confirmar su picking si está en borrador
                    for move in moves_with_dest:
                        for dest_move in move.move_dest_ids:
                            try:
                                if dest_move.picking_id and dest_move.picking_id.exists():
                                    dest_picking = dest_move.picking_id
                                    if dest_picking.state == 'draft':
                                        _logger.info("Confirmando automáticamente picking %s creado desde move_dest_ids", 
                                                   dest_picking.name or dest_picking.id)
                                        dest_picking.action_confirm()
                            except Exception as e:
                                _logger.warning("Error al confirmar picking destino: %s", str(e))
                                continue
        except Exception as e:
            _logger.warning("Error al procesar confirmación automática de pickings destino: %s", str(e))
        
        return res

    def _is_client_stock_location(self, location):
        """
        True si la ubicación es "stock del cliente": uso customer, o (sub)ubicación de un almacén con partner.
        Incluye la ubicación y cualquier hijo (ej. SOCIE/Existencias).
        """
        if not location or not location.exists():
            return False
        # La propia ubicación tiene uso customer
        if getattr(location, 'usage', None) == 'customer':
            return True
        # Almacén de cliente: warehouse con partner_id cuya lot_stock_id es esta ubicación
        wh = self.env['stock.warehouse'].sudo().search([
            ('lot_stock_id', '=', location.id),
            ('partner_id', '!=', False),
        ], limit=1)
        if wh:
            return True
        # Ubicación hija de una con uso customer (ej. Cliente/Existencias)
        parent = location.location_id
        while parent and parent.exists():
            if getattr(parent, 'usage', None) == 'customer':
                return True
            wh_parent = self.env['stock.warehouse'].sudo().search([
                ('lot_stock_id', '=', parent.id),
                ('partner_id', '!=', False),
            ], limit=1)
            if wh_parent:
                return True
            parent = parent.location_id
        return False

    def _is_return_picking_type(self, picking):
        """True solo si el tipo de operación es de devolución (no entrega, alistamiento, etc.)."""
        if not picking or not picking.exists() or not picking.picking_type_id:
            return False
        name = (picking.picking_type_id.name or '').lower()
        return 'devolución' in name or 'devolucion' in name

    def _set_renting_exit_date_on_return(self):
        """
        Cuando el picking está hecho y algún movimiento SACA producto de una ubicación de cliente,
        actualiza Fecha Finalizacion Renting (exit_date) en los lotes. No depende del nombre del
        tipo de operación (p. ej. aunque no se llame "Devolución"). No toca entregas (destino = cliente).
        """
        today = fields.Date.context_today(self)
        for picking in self:
            if picking.state != 'done' or not picking.exists():
                continue
            for move in picking.move_ids:
                if move.state != 'done':
                    continue
                src = move.location_id
                if not self._is_client_stock_location(src):
                    continue
                for line in move.move_line_ids:
                    if not line.lot_id or not line.lot_id.exists():
                        continue
                    lot = line.lot_id
                    if not hasattr(lot, 'exit_date'):
                        continue
                    lot.sudo().write({'exit_date': today})
                    _logger.info(
                        "Actualizada Fecha Finalizacion Renting (exit_date=%s) en lote %s (salida desde ubicación cliente %s)",
                        today, lot.name, src.complete_name
                    )

    def _clear_renting_dates_on_delivery_to_client(self):
        """
        Cuando el picking es una ENTREGA al cliente (producto entra a ubicación de cliente),
        limpia exit_date y last_exit_date_display en los lotes y establece entry_date a la
        fecha de la entrega, para que "Tiempo En Sitio" y "Días En Sitio" cuenten desde la
        reentrega (mismo equipo entregado de nuevo al cliente).
        """
        today = fields.Date.context_today(self)
        for picking in self:
            if picking.state != 'done' or not picking.exists():
                continue
            if self._is_return_picking_type(picking):
                continue
            # Fecha de la entrega: date_done del picking o hoy
            delivery_date = today
            if picking.date_done:
                delivery_date = (
                    picking.date_done.date()
                    if hasattr(picking.date_done, 'date') else picking.date_done
                )
            for move in picking.move_ids:
                if move.state != 'done':
                    continue
                dest = move.location_dest_id
                if not dest or not self._is_client_stock_location(dest):
                    continue
                for line in move.move_line_ids:
                    if not line.lot_id or not line.lot_id.exists():
                        continue
                    lot = line.lot_id
                    vals = {}
                    if hasattr(lot, 'exit_date') and lot.exit_date:
                        vals['exit_date'] = False
                    if hasattr(lot, 'last_exit_date_display') and lot.last_exit_date_display:
                        vals['last_exit_date_display'] = False
                    # Siempre actualizar entry_date a la fecha de esta entrega para que Tiempo En Sitio cuente desde la reentrega
                    if hasattr(lot, 'entry_date'):
                        vals['entry_date'] = delivery_date
                    if not vals:
                        continue
                    lot.sudo().write(vals)
                    _logger.info(
                        "Entrega al cliente: lote %s - entry_date=%s, fechas salida limpiadas (%s)",
                        lot.name, delivery_date, dest.complete_name
                    )
                    # Refrescar la suscripción para que la vista muestre las nuevas fechas
                    if hasattr(lot, 'active_subscription_id') and lot.active_subscription_id and hasattr(lot.active_subscription_id, 'invalidate_recordset'):
                        lot.active_subscription_id.invalidate_recordset(['grouped_product_ids'])

    @api.model
    def action_backfill_renting_exit_dates(self):
        """
        Actualiza Fecha Finalizacion Renting (exit_date) en lotes de devoluciones ya validadas.
        Busca todos los movimientos hechos que salieron de una ubicación de cliente y asigna
        exit_date = fecha del movimiento a cada lote involucrado (para que la suscripción calcule bien).
        """
        updated = 0
        Move = self.env['stock.move'].sudo()
        done_moves = Move.search([
            ('state', '=', 'done'),
            ('location_id', '!=', False),
        ])
        for move in done_moves:
            if not move.picking_id or not self._is_return_picking_type(move.picking_id):
                continue
            if not self._is_client_stock_location(move.location_id):
                continue
            # Fecha del movimiento (cuando se hizo la devolución)
            move_date = None
            if move.picking_id and move.picking_id.date_done:
                move_date = (move.picking_id.date_done.date()
                             if hasattr(move.picking_id.date_done, 'date') else move.picking_id.date_done)
            elif move.date:
                move_date = (move.date.date() if hasattr(move.date, 'date') else move.date)
            if not move_date:
                continue
            for line in move.move_line_ids:
                if not line.lot_id or not line.lot_id.exists() or not hasattr(line.lot_id, 'exit_date'):
                    continue
                line.lot_id.sudo().write({'exit_date': move_date})
                updated += 1
                _logger.info(
                    "Backfill: exit_date=%s en lote %s (movimiento %s)",
                    move_date, line.lot_id.name, move.picking_id.name if move.picking_id else move.id
                )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fecha Finalizacion Renting actualizada'),
                'message': _('Se actualizó exit_date en %s lote(s) de devoluciones ya validadas.') % updated,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_clear_exit_date_from_deliveries(self):
        """
        Corrige lotes a los que se les puso Fecha Finalizacion Renting por error al validar
        una ENTREGA (Alistamiento, Transporte, etc.). Solo limpia exit_date cuando el último
        movimiento desde ubicación de cliente de ese lote NO fue una devolución.
        """
        Lot = self.env['stock.lot'].sudo()
        lots_with_exit = Lot.search([('exit_date', '!=', False)])
        if not hasattr(Lot, 'exit_date'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin cambios'),
                    'message': _('El modelo de lote no tiene campo exit_date.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        cleared = 0
        for lot in lots_with_exit:
            lines = self.env['stock.move.line'].sudo().search([
                ('lot_id', '=', lot.id),
                ('move_id.state', '=', 'done'),
                ('move_id.location_id', '!=', False),
            ])
            lines_from_client = lines.filtered(lambda l: self._is_client_stock_location(l.move_id.location_id))
            if not lines_from_client:
                continue
            # Ordenar por fecha del movimiento (más reciente primero)
            def _move_done_date(ml):
                p = ml.move_id.picking_id
                d = p.date_done if p and p.date_done else ml.move_id.date
                if d and hasattr(d, 'date'):
                    return d.date()
                return d or fields.Date.from_string('1900-01-01')
            most_recent_line = max(lines_from_client, key=_move_done_date)
            picking = most_recent_line.move_id.picking_id
            if self._is_return_picking_type(picking):
                continue
            lot.sudo().write({'exit_date': False})
            cleared += 1
            _logger.info(
                "Corrección: quitada exit_date del lote %s (último movimiento desde cliente fue entrega: %s)",
                lot.name, picking.picking_type_id.name if picking and picking.picking_type_id else 'N/A'
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Corrección aplicada'),
                'message': _('Se quitó Fecha Finalizacion Renting en %s lote(s) que la tenían por error (entregas).') % cleared,
                'type': 'success',
                'sticky': False,
            },
        }

    def _log_supplies_purchase_history(self):
        """Registra el historial de compras de componentes/periféricos/complementos."""
        try:
            History = self.env["supplies.item.history"]

            # CORRECCIÓN: Validar que picking_type_id existe antes de acceder a code
            for picking in self.filtered(lambda p: p.picking_type_id and p.picking_type_id.exists() and p.picking_type_id.code == "incoming"):
                try:
                    default_date = picking.date_done or fields.Datetime.now()
                    partner = picking.partner_id

                    moves = getattr(picking, 'move_ids_without_package', picking.move_ids)
                    for move in moves:
                        try:
                            kind = move.supply_kind
                            if kind not in ("component", "peripheral", "complement"):
                                continue

                            # CORRECCIÓN: Validar que purchase_line_id existe antes de acceder
                            parent_prod = False
                            if move.supply_parent_product_id and move.supply_parent_product_id.exists():
                                parent_prod = move.supply_parent_product_id
                            elif move.purchase_line_id and move.purchase_line_id.exists() and move.purchase_line_id.product_id:
                                parent_prod = move.purchase_line_id.product_id
                            parent_tmpl = parent_prod.product_tmpl_id if parent_prod and parent_prod.exists() else False

                            # CORRECCIÓN: Validar que purchase_line_id y order_id existen antes de acceder
                            po = False
                            if move.purchase_line_id and move.purchase_line_id.exists():
                                if move.purchase_line_id.order_id and move.purchase_line_id.order_id.exists():
                                    po = move.purchase_line_id.order_id
                            po_date = getattr(po, "date_order", False) if po else def