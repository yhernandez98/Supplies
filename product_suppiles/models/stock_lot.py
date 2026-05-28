# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning
import logging
from urllib.parse import quote
import json
from dateutil.relativedelta import relativedelta

try:
    from lxml import etree
except ImportError:
    etree = None

_logger = logging.getLogger(__name__)
_logger.info("[product_supplies] módulo stock_lot cargado (si ves esto, el módulo está activo)")


def _inject_supplies_notebook_into_form_arch(env, arch):
    """Si la vista XML no aplicó nuestro notebook, lo inyectamos antes del chatter (fallback)."""
    import traceback
    _logger.info("[product_supplies] stock.lot form: _inject_supplies_notebook_into_form_arch llamado")
    try:
        if etree is None:
            _logger.warning("[product_supplies] stock.lot form: lxml no disponible, no se puede inyectar notebook")
            return arch
        arch_str = arch.decode('utf-8') if isinstance(arch, bytes) else (arch if isinstance(arch, str) else None)
        if arch_str is None:
            try:
                arch_str = etree.tostring(arch, encoding='unicode')
            except Exception as e:
                _logger.warning("[product_supplies] stock.lot form: no se pudo convertir arch a string: %s", e)
                return arch
        if 'name="info_group"' in arch_str or 'name=\'info_group\'' in arch_str:
            _logger.info("[product_supplies] stock.lot form: vista XML ya tiene pestañas (info_group), no inyectar")
            return arch
        view = env['ir.ui.view'].search([
            ('model', '=', 'stock.lot'), ('type', '=', 'form'),
            ('name', '=', 'production.lot.form.supplies.inherit')
        ], limit=1)
        if not view:
            _logger.warning(
                "[product_supplies] stock.lot form: vista 'production.lot.form.supplies.inherit' NO existe en BD. "
                "Actualiza el módulo Product Supplies y revisa que no haya errores al cargar el XML."
            )
            return arch
        if not (getattr(view, 'arch_db', None) or getattr(view, 'arch', None)):
            _logger.warning("[product_supplies] stock.lot form: vista encontrada pero sin arch_db/arch")
            return arch
        view = view.sudo()
        raw = view.arch_db if view.arch_db else (getattr(view, 'arch', None) or '')
        if not raw:
            _logger.warning("[product_supplies] stock.lot form: vista arch vacío")
            return arch
        raw = raw.encode('utf-8') if isinstance(raw, str) else raw
        root_supplies = etree.fromstring(raw)
        xpath_before_chatter = root_supplies.xpath("//*[contains(@expr, 'chatter') and @position='before']")
        if not xpath_before_chatter:
            xpath_before_chatter = root_supplies.xpath("//*[contains(@expr, 'chatter')]")
        notebook_node = None
        for xp in xpath_before_chatter:
            for child in xp:
                tag = child.tag if hasattr(child, 'tag') else None
                local_tag = (tag.split('}')[-1] if tag and '}' in tag else tag) or ''
                if local_tag == 'notebook':
                    notebook_node = child
                    break
            if notebook_node is not None:
                break
        if notebook_node is None:
            _logger.warning(
                "[product_supplies] stock.lot form: en la vista no se encontró nodo <notebook> dentro del xpath chatter. "
                "Revisa que stock_lot_form_supplies_inherit.xml tenga <xpath expr=\"//chatter\" position=\"before\"><notebook>..."
            )
            return arch
        root = etree.fromstring(arch_str.encode('utf-8') if isinstance(arch_str, str) else arch_str)
        chatter_list = root.xpath("//chatter") or root.xpath("//*[local-name()='chatter']")
        if not chatter_list:
            _logger.warning("[product_supplies] stock.lot form: en la vista combinada no hay <chatter>, no se puede inyectar")
            return arch
        parent = chatter_list[0].getparent()
        idx = list(parent).index(chatter_list[0])
        import copy
        new_notebook = copy.deepcopy(notebook_node)
        parent.insert(idx, new_notebook)
        out = etree.tostring(root, encoding='unicode')
        _logger.info("[product_supplies] stock.lot form: notebook inyectado correctamente por fallback Python")
        return out
    except Exception as e:
        _logger.exception(
            "[product_supplies] stock.lot form: ERROR en _inject_supplies_notebook_into_form_arch: %s\n%s",
            e, traceback.format_exc()
        )
        return arch


class StockLot(models.Model):
    _inherit = "stock.lot"

    model_name = fields.Char(string="Modelo")
    inventory_plate = fields.Char(string="Placa de Inventario")
    security_plate = fields.Char(string="Placa de Seguridad")
    billing_code = fields.Char(string="Código de Facturación")

    cost_additional = fields.Boolean(
        string="Costo Adicional",
        default=False,
        help="Check para marcar costo adicional. Solo se muestra para productos clasificados como Componente, Complemento o Periférico.",
    )
    cost_additional_value = fields.Float(
        string="Valor Costo Adicional",
        digits=(16, 2),
        default=0.0,
        help="Valor adicional manual cuando se activa la opción Costo Adicional.",
    )

    @api.onchange("cost_additional")
    def _onchange_cost_additional_reset_value(self):
        """
        Regla de UI:
        - Si se desmarca "Costo Adicional", el valor debe quedar en 0.0.
        - Pero si este serial ya está asociado como elemento (related_lot_id) a otro producto,
          no se permite desmarcar hasta que primero se desasocie.
        """
        for lot in self:
            if lot.id and not lot.cost_additional:
                SupplyLine = self.env["stock.lot.supply.line"]
                # ¿Este serial (lot) está usando este lote como componente/periférico asociado?
                links = SupplyLine.search([("related_lot_id", "=", lot.id), ("has_cost", "=", True)])
                if links:
                    principal_products = links.mapped("lot_id.product_id").filtered(lambda p: p)
                    principal_product_names = sorted(set(principal_products.mapped("display_name")))

                    # Restaurar el checkbox y conservar el valor anterior (para que no se pierda).
                    previous_cost_additional = bool(getattr(lot._origin, "cost_additional", False))
                    previous_value = float(getattr(lot._origin, "cost_additional_value", 0.0) or 0.0)
                    lot.cost_additional = previous_cost_additional or True
                    lot.cost_additional_value = previous_value

                    tab_message = ", ".join(principal_product_names) if principal_product_names else _("(sin producto)")
                    return {
                        "warning": {
                            "title": _("Serial asociado"),
                            "message": _(
                                "Este serial está asociado a: %(products)s. "
                                "Primero debes desasociarlo y luego podrás desmarcar 'Costo Adicional'."
                            )
                            % {"products": tab_message},
                        }
                    }

            if not lot.cost_additional:
                lot.cost_additional_value = 0.0

    def _get_principal_products_for_associated_serial(self):
        """Devuelve nombres de productos principales donde este serial está asociado como related_lot_id."""
        SupplyLine = self.env["stock.lot.supply.line"]
        links = SupplyLine.search([("related_lot_id", "in", self.ids), ("has_cost", "=", True)])
        principal_products = links.mapped("lot_id.product_id").filtered(lambda p: p)
        return sorted(set(principal_products.mapped("display_name")))

    def _get_lot_supply_editor_wizard_url(self, principal_lot):
        """
        Construye una URL para abrir el wizard de edición de elementos asociados
        (`lot.supply.editor.wizard`) ya prellenado con el lote principal.
        """
        if not principal_lot:
            return ""
        try:
            action_id = self.env.ref("product_suppiles.action_lot_supply_editor_wizard").id
        except Exception:
            action_id = None
        if not action_id:
            return ""

        context = {"default_lot_id": principal_lot.id}
        context_str = quote(json.dumps(context))
        # Odoo web client: /web#action=<id>&model=<model>&view_type=form&context=<json>
        return "/web#action=%s&model=lot.supply.editor.wizard&view_type=form&context=%s" % (
            action_id,
            context_str,
        )
    entry_date = fields.Date(
        string="Fecha Activacion Renting",
        help="Fecha en que el producto llegó a la ubicación del cliente. Se usa para facturación prorrateada por días (solo productos/servicios, no licencias)."
    )
    last_entry_date_display = fields.Date(
        string="Última Fecha Activación (hasta limpieza)",
        readonly=True,
        help="Copia de la última fecha de activación; se conserva si se borra entry_date hasta que el módulo haga la limpieza o se quite la suscripción del serial."
    )
    entry_date_display = fields.Date(
        string="Fecha activación (visible en suscripción)",
        compute="_compute_entry_date_display",
        readonly=True,
        help="Lo que ve la suscripción: Fecha Activación si está puesta, o la última conservada al borrar."
    )
    exit_date = fields.Date(
        string="Fecha Finalizacion Renting",
        help="Fecha en que el producto salió de la ubicación del cliente. Se usa para facturación prorrateada por días (solo productos/servicios, no licencias)."
    )
    last_exit_date_display = fields.Date(
        string="Última Fecha Salida (hasta limpieza)",
        readonly=True,
        help="Copia de la última fecha de salida; se conserva si se borra exit_date (p. ej. equipo a otro cliente) hasta que el módulo haga la limpieza del primer día del mes o se quite la suscripción del serial."
    )
    exit_date_display = fields.Date(
        string="Fecha finalización (visible en suscripción)",
        compute="_compute_exit_date_display",
        readonly=True,
        help="Lo que ve la suscripción: Fecha Finalizacion si está puesta, o la última fecha de salida conservada al borrar."
    )

    @api.depends("exit_date", "last_exit_date_display")
    def _compute_exit_date_display(self):
        """Coincide con lo que muestra la suscripción al usar exit_date o last_exit_date_display."""
        for lot in self:
            lot.exit_date_display = lot.exit_date or lot.last_exit_date_display or False

    @api.depends("entry_date", "last_entry_date_display")
    def _compute_entry_date_display(self):
        """Coincide con lo que muestra la suscripción al usar entry_date o last_entry_date_display."""
        for lot in self:
            lot.entry_date_display = lot.entry_date or lot.last_entry_date_display or False

    reining_plazo = fields.Selection(
        [
            ("12", "12 meses"),
            ("24", "24 meses"),
            ("36", "36 meses"),
            ("48", "48 meses"),
            ("60", "60 meses"),
            ("sin_permanencia", "Sin Permanencia"),
        ],
        string="Plazo Renting",
        help="Plazo Renting en meses. Sin Permanencia: sin fecha de finalización fija.",
    )
    reining_plazo_custom_months = fields.Integer(
        string="Meses (personalizado)",
        help="Solo cuando Plazo Renting es Fecha personalizada. Ej: 18, 72.",
    )
    hostname = fields.Char(
        string="Hostname",
        help="Nombre de host o nombre del equipo en la red",
        tracking=True
    )

    def get_acta_reining_plazo_label(self):
        """Etiqueta legible del plazo renting para actas PDF (QWeb)."""
        self.ensure_one()
        if "reining_plazo" not in self._fields:
            return ""
        val = self.reining_plazo
        if not val:
            return ""
        sel = self._fields["reining_plazo"].selection
        pairs = sel(self) if callable(sel) else (sel or [])
        return dict(pairs).get(val, val)

    def get_acta_entrega_subscription_service_price_safe(self):
        """Precio recurrente del servicio para PDF; vacío si no aplica o no está el módulo de suscripción."""
        self.ensure_one()
        fn = getattr(self, "get_acta_entrega_subscription_service_price_display", None)
        if not callable(fn):
            return ""
        try:
            return fn() or ""
        except Exception:
            return ""

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            _logger.info("[product_supplies] stock.lot _get_view: form solicitado, aplicando fallback de notebook")
            arch = _inject_supplies_notebook_into_form_arch(self.env, arch)
        return (arch, view)

    @api.model
    def action_log_supplies_view_debug(self):
        """Escribe en el log del servidor el estado de las vistas de formulario stock.lot (para depurar)."""
        View = self.env['ir.ui.view'].sudo()
        form_views = View.search([
            ('model', '=', 'stock.lot'),
            ('type', '=', 'form'),
        ], order='priority asc, id asc')
        supplies = form_views.filtered(lambda v: v.name == 'production.lot.form.supplies.inherit')
        lines = [
            "[product_supplies] === DEBUG VISTAS stock.lot (form) ===",
            "Total vistas form stock.lot: %s" % len(form_views),
            "Vista 'production.lot.form.supplies.inherit' existe: %s" % bool(supplies),
        ]
        if supplies:
            v = supplies[0]
            lines.append("  - id: %s, priority: %s, inherit_id: %s, activa: %s" % (
                v.id, v.priority, v.inherit_id.id if v.inherit_id else None, getattr(v, 'active', True)))
            lines.append("  - arch_db presente: %s (len %s)" % (bool(v.arch_db), len(v.arch_db or '')))
        for v in form_views[:15]:
            lines.append("  Vista: name=%s id=%s priority=%s inherit_id=%s" % (
                (v.name or '')[:50], v.id, v.priority, v.inherit_id.id if v.inherit_id else None))
        msg = "\n".join(lines)
        _logger.info(msg)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug vistas'),
                'message': _('Revisa el LOG del servidor Odoo. Busca "[product_supplies]".'),
                'type': 'info',
                'sticky': False,
            }
        }

    def _get_exit_date_from_plazo(self, entry_date, reining_plazo, custom_months=0):
        """Calcula Fecha Finalizacion Renting a partir de Fecha Activacion y Plazo Renting.
        Sin Permanencia -> devuelve False (sin fecha de fin)."""
        if not entry_date or not reining_plazo:
            return False
        if reining_plazo == "sin_permanencia":
            return False
        if reining_plazo == "custom" and custom_months:
            months = custom_months
        elif reining_plazo in ("12", "24", "36", "48", "60"):
            months = int(reining_plazo)
        else:
            return False
        if months <= 0:
            return False
        if hasattr(entry_date, "year"):
            d = entry_date
        else:
            d = fields.Date.from_string(entry_date) if entry_date else None
        if not d:
            return False
        return d + relativedelta(months=months)

    @api.onchange("reining_plazo", "entry_date", "reining_plazo_custom_months")
    def _onchange_plazo_compute_exit_date(self):
        """Rellena Fecha Finalizacion Renting según Plazo Renting y Fecha Activacion."""
        for lot in self:
            exit_d = lot._get_exit_date_from_plazo(
                lot.entry_date,
                lot.reining_plazo,
                lot.reining_plazo_custom_months or 0,
            )
            lot.exit_date = exit_d

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Seguridad: nunca persistir valor si el checkbox "Costo Adicional" llega como False.
            if "cost_additional" in vals and not vals.get("cost_additional"):
                vals["cost_additional_value"] = 0.0
            elif "cost_additional_value" in vals and not vals.get("cost_additional", False):
                vals["cost_additional_value"] = 0.0

            entry = vals.get("entry_date")
            plazo = vals.get("reining_plazo")
            custom = vals.get("reining_plazo_custom_months", 0)
            if entry and plazo and "exit_date" not in vals:
                exit_d = self._get_exit_date_from_plazo(entry, plazo, custom)
                if exit_d:
                    vals["exit_date"] = exit_d
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("skip_lot_date_history"):
            return super().write(vals)

        previous_entry_dates = {}
        previous_exit_dates = {}
        if "entry_date" in vals and not vals["entry_date"]:
            previous_entry_dates = {
                lot.id: lot.entry_date for lot in self if lot.id and lot.entry_date
            }
        if "exit_date" in vals and not vals["exit_date"]:
            previous_exit_dates = {
                lot.id: lot.exit_date for lot in self if lot.id and lot.exit_date
            }

        # Validación server-side: no permitir desmarcar el checkbox si este serial
        # está asociado como elemento (related_lot_id) en alguna línea de suministro.
        if "cost_additional" in vals and vals.get("cost_additional") is False:
            for lot in self:
                if not lot.id:
                    continue
                SupplyLine = self.env["stock.lot.supply.line"]
                links = SupplyLine.search([("related_lot_id", "=", lot.id), ("has_cost", "=", True)])
                if links:
                    principal_products = links.mapped("lot_id.product_id").filtered(lambda p: p)
                    products_txt = ", ".join(sorted(set(principal_products.mapped("display_name")))) or _("(sin producto)")

                    principal_lots = links.mapped("lot_id").filtered(lambda l: l and l.exists())
                    principal_lot = principal_lots[:1]

                    action_id = False
                    try:
                        action_id = self.env.ref("product_suppiles.action_lot_supply_editor_wizard").id
                    except Exception:
                        action_id = False

                    message = _(
                        "Este serial está asociado a: %(products)s. "
                        "Primero debes desasociarlo en el wizard y luego podrás desmarcar 'Costo Adicional'."
                    ) % {"products": products_txt}

                    if action_id and principal_lot:
                        raise RedirectWarning(
                            message,
                            action_id,
                            _("Abrir wizard para desasociar"),
                            additional_context={
                                "default_lot_id": principal_lot.id,
                                # Serial que intentamos desmarcar; el wizard lo desasocia de forma forzada al guardar.
                                "force_unlink_related_lot_id": lot.id,
                            },
                        )
                    raise UserError(message)

        # Seguridad: si se desmarca "Costo Adicional" y se está guardando, limpiar el valor en servidor.
        # Esto evita que el valor anterior vuelva a persistirse si el cliente no envía el campo
        # cuando queda en readonly.
        if "cost_additional" in vals and not vals.get("cost_additional"):
            vals["cost_additional_value"] = 0.0

        if "reining_plazo" in vals or "entry_date" in vals or "reining_plazo_custom_months" in vals:
            for lot in self:
                entry = vals.get("entry_date", lot.entry_date)
                plazo = vals.get("reining_plazo", lot.reining_plazo)
                custom = vals.get("reining_plazo_custom_months", lot.reining_plazo_custom_months or 0)
                if entry and plazo and "exit_date" not in vals:
                    exit_d = lot._get_exit_date_from_plazo(entry, plazo, custom)
                    vals.setdefault("exit_date", exit_d if exit_d else lot.exit_date)
                elif plazo == "sin_permanencia" and "exit_date" not in vals:
                    vals.setdefault("exit_date", False)
        # Conservar última fecha de activación para mostrar en suscripción al borrar entry_date
        if "entry_date" in vals:
            if vals["entry_date"]:
                vals["last_entry_date_display"] = vals["entry_date"]
        # Conservar última fecha de salida para mostrar en suscripción hasta la limpieza
        if "exit_date" in vals:
            if vals["exit_date"]:
                vals["last_exit_date_display"] = vals["exit_date"]
            elif "last_exit_date_display" in vals:
                # No pasar last_exit_date_display en vals para que ningún otro write lo pise
                vals = {k: v for k, v in vals.items() if k != "last_exit_date_display"}
        res = super().write(vals)
        if previous_entry_dates:
            for lot in self.filtered(lambda l: l.id in previous_entry_dates and not l.entry_date):
                super(StockLot, lot.with_context(skip_lot_date_history=True)).write({
                    "last_entry_date_display": previous_entry_dates[lot.id],
                })
        if previous_exit_dates:
            for lot in self.filtered(lambda l: l.id in previous_exit_dates and not l.exit_date):
                super(StockLot, lot.with_context(skip_lot_date_history=True)).write({
                    "last_exit_date_display": previous_exit_dates[lot.id],
                })
        # Refrescar productos agrupados de la suscripción para que muestre last_exit_date_display
        if "exit_date" in vals and not vals.get("exit_date"):
            for lot in self:
                sub = getattr(lot, "active_subscription_id", None)
                if sub and hasattr(sub, "invalidate_recordset"):
                    sub.invalidate_recordset(["grouped_product_ids"])
                    break
        return res

    is_principal = fields.Boolean(
        string="Es principal",
        help="Marcado automáticamente cuando el lote/serie es del producto principal en la recepción."
    )
    principal_product_id = fields.Many2one(
        "product.product",
        string="Producto principal (recepción)",
        help="Producto principal con el cual se asocia este lote/serie (si este lote es de un periférico/component/complement).",
        index=True,
    )
    principal_lot_id = fields.Many2one(
        "stock.lot",
        string="Lote/Serie principal (recepción)",
        domain="[('product_id', '=', principal_product_id)]",
        help="Lote/Serie del producto principal en esta misma recepción (si aplica)."
    )
    purchase_tracking_ref = fields.Char(
        string="Seguimiento compra",
        help="PO/Picking de origen; rellenado automáticamente en la validación de la recepción."
    )

    lot_classification = fields.Selection(
        related="product_id.classification", store=True, readonly=True
    )
    asset_category_id = fields.Many2one(
        "product.asset.category",
        related="product_id.asset_category_id",
        readonly=True,
        store=False,
    )
    asset_class_id = fields.Many2one(
        "product.asset.class",
        related="product_id.asset_class_id",
        readonly=True,
        store=False,
    )
    show_subscription_service_fields = fields.Boolean(
        string="Mostrar servicio/suscripción",
        compute="_compute_show_subscription_service_fields",
        store=False,
    )

    component_product_ids = fields.Many2many(
        "product.product", string="Componentes (producto)",
        compute="_compute_related_supplies", store=False
    )
    peripheral_product_ids = fields.Many2many(
        "product.product", string="Periféricos (producto)",
        compute="_compute_related_supplies", store=False
    )
    complement_product_ids = fields.Many2many(
        "product.product", string="Complementos (producto)",
        compute="_compute_related_supplies", store=False
    )
    lot_supply_line_ids = fields.One2many(
        "stock.lot.supply.line", "lot_id", string="Líneas de Suministros (por Serie)"
    )
    # Mismo modelo e inverse (lot_id), con dominio: así las líneas nuevas se crean por el flujo normal y el contexto default_has_cost se aplica en create()
    lot_supply_line_sin_costo_ids = fields.One2many(
        "stock.lot.supply.line",
        "lot_id",
        string="Elementos Sin Costo",
        domain=[("has_cost", "=", False)],
    )
    lot_supply_line_con_costo_ids = fields.One2many(
        "stock.lot.supply.line",
        "lot_id",
        string="Elementos Con Costo",
        domain=[("has_cost", "=", True)],
    )

    current_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación actual",
        compute="_compute_current_location_id",
        store=False,
        help="Ubicación interna donde existe stock positivo de este lote/serie (primera encontrada)."
    )
    
    # Campos para mostrar información cuando este lote está asociado a otro producto principal
    is_associated_element = fields.Boolean(
        string="Es Elemento Asociado",
        compute="_compute_is_associated_element",
        store=False,
        help="Indica si este serial está asociado como elemento (componente/periférico/complemento) a otro producto principal."
    )
    
    associated_to_principal_lot_id = fields.Many2one(
        "stock.lot",
        string="Producto Principal",
        compute="_compute_is_associated_element",
        store=False,
        help="Producto principal al que está asociado este elemento."
    )
    
    associated_to_principal_product_id = fields.Many2one(
        "product.product",
        string="Producto Principal (Producto)",
        compute="_compute_is_associated_element",
        store=False,
        help="Producto principal (producto) al que está asociado este elemento."
    )
    
    associated_item_type = fields.Selection(
        [("component", "Componente"), ("peripheral", "Periférico"), ("complement", "Complemento"), ("monitor", "Monitores"), ("ups", "UPS")],
        string="Tipo de Asociación",
        compute="_compute_is_associated_element",
        store=False,
        help="Tipo de elemento asociado (componente, periférico, complemento, monitores o UPS)."
    )
    
    associated_to_principal_inventory_plate = fields.Char(
        string="Placa de Inventario Principal",
        compute="_compute_is_associated_element",
        store=False,
        help="Placa de inventario del producto principal al que está asociado este elemento."
    )
    
    # Campo para detectar seriales con cantidad > 1
    has_excess_quantity = fields.Boolean(
        string="Cantidad > 1",
        compute="_compute_has_excess_quantity",
        store=False,
        search="_search_has_excess_quantity",
        help="Indica si este serial tiene una cantidad a la mano mayor a 1 (debería ser siempre 1)"
    )
    
    def _compute_has_excess_quantity(self):
        """Calcula si el serial tiene cantidad > 1."""
        for lot in self:
            lot.has_excess_quantity = lot.product_qty > 1.0 if lot.product_qty else False
    
    @api.model
    def _search_has_excess_quantity(self, operator, value):
        """Permite buscar seriales con cantidad > 1."""
        try:
            # ORM: mantener reglas de acceso y transaccionalidad sin SQL manual.
            grouped = self.env["stock.quant"].read_group(
                domain=[("lot_id", "!=", False), ("quantity", ">", 0)],
                fields=["lot_id", "quantity:sum"],
                groupby=["lot_id"],
                lazy=False,
            )
            lot_ids = [
                row["lot_id"][0]
                for row in grouped
                if row.get("lot_id") and (row.get("quantity", 0.0) or 0.0) > 1.0
            ]
            
            # Si no hay resultados, retornar dominio que no coincida con nada
            if not lot_ids:
                lot_ids = [-1]  # ID que no existe
            
            # Manejar diferentes operadores
            if operator == '=' and value:
                # Buscar lotes con cantidad > 1
                return [('id', 'in', lot_ids)]
            elif operator == '=' and not value:
                # Buscar lotes con cantidad <= 1 (todos menos los de lot_ids)
                return [('id', 'not in', lot_ids if lot_ids != [-1] else [])]
            elif operator == '!=' and value:
                # Buscar lotes con cantidad <= 1
                return [('id', 'not in', lot_ids if lot_ids != [-1] else [])]
            elif operator == '!=' and not value:
                # Buscar lotes con cantidad > 1
                return [('id', 'in', lot_ids)]
            else:
                # Por defecto, retornar los lotes con cantidad > 1
                return [('id', 'in', lot_ids)]
        except Exception as e:
            # En caso de error, retornar dominio vacío
            _logger.warning("Error en _search_has_excess_quantity: %s", str(e))
            return [('id', '=', False)]


    def _compute_current_location_id(self):
        """Calcula la ubicación actual del lote, protegido contra errores durante instalación."""
        Quant = self.env["stock.quant"]
        for lot in self:
            lot.current_location_id = False
            if not lot.id:
                continue
            # Proteger contra errores durante instalación/actualización
            try:
                # Buscamos una ubicación interna con stock positivo
                quant = Quant.search([
                    ("lot_id", "=", lot.id),
                    ("quantity", ">", 0),
                    ("location_id.usage", "=", "internal"),
                ], order="in_date desc, id desc", limit=1)
                lot.current_location_id = quant.location_id if quant else False
            except Exception:
                # Si hay error (por ejemplo, durante instalación), dejar en False
                lot.current_location_id = False

    @api.depends("lot_classification", "asset_category_id", "asset_class_id")
    def _compute_show_subscription_service_fields(self):
        for lot in self:
            default_visible = lot.lot_classification not in ("component", "complement", "spare")
            category_name = (lot.asset_category_id.name or "").strip().lower()
            class_name = (lot.asset_class_id.name or "").strip().lower()
            complement_phone_exception = (
                lot.lot_classification == "complement"
                and category_name == "telefonia"
                and class_name == "telefono"
            )
            lot.show_subscription_service_fields = default_visible or complement_phone_exception
    
    def _compute_is_associated_element(self):
        """Calcula si este lote está asociado como elemento a otro producto principal."""
        for lot in self:
            lot.is_associated_element = False
            lot.associated_to_principal_lot_id = False
            lot.associated_to_principal_product_id = False
            lot.associated_item_type = False
            lot.associated_to_principal_inventory_plate = False
            
            if not lot.id:
                continue
            
            # Buscar si este lote está en alguna línea de suministro como related_lot_id
            try:
                # Verificar que el modelo existe antes de buscar
                if 'stock.lot.supply.line' not in self.env:
                    continue
                
                SupplyLine = self.env['stock.lot.supply.line']
                supply_line = SupplyLine.search([
                    ('related_lot_id', '=', lot.id)
                ], limit=1)
                
                if supply_line and supply_line.lot_id and supply_line.lot_id.exists():
                    principal_lot = supply_line.lot_id
                    lot.is_associated_element = True
                    lot.associated_to_principal_lot_id = principal_lot
                    lot.associated_to_principal_product_id = principal_lot.product_id
                    lot.associated_item_type = supply_line.item_type
                    lot.associated_to_principal_inventory_plate = principal_lot.inventory_plate or ''
            except Exception:
                # Si hay error, dejar en False
                pass

    @api.depends("product_id", "product_id.product_tmpl_id",
                 "product_id.product_tmpl_id.composite_line_ids",
                 "product_id.product_tmpl_id.peripheral_line_ids",
                 "product_id.product_tmpl_id.complement_line_ids")
    def _compute_related_supplies(self):
        for lot in self:
            tmpl = lot.product_id.product_tmpl_id
            if not tmpl:
                lot.component_product_ids = False
                lot.peripheral_product_ids = False
                lot.complement_product_ids = False
                continue

            comps = tmpl.composite_line_ids.mapped("component_product_id")
            peris = tmpl.peripheral_line_ids.mapped("peripheral_product_id")
            compl = tmpl.complement_line_ids.mapped("complement_product_id")

            lot.component_product_ids = comps.ids
            lot.peripheral_product_ids = peris.ids
            lot.complement_product_ids = compl.ids

    def name_get(self):
        """Personaliza el nombre mostrado para priorizar la placa de inventario."""
        result = []
        for lot in self:
            name_parts = []
            # Priorizar placa de inventario si existe
            if lot.inventory_plate:
                name_parts.append(lot.inventory_plate)
            # Agregar número de serie si existe
            if lot.name:
                name_parts.append("Serie: %s" % lot.name)
            # Agregar producto si existe
            if lot.product_id:
                name_parts.append(lot.product_id.display_name)
            # Si no hay nada, usar el nombre por defecto
            if not name_parts:
                name_parts.append(lot.name or "Lote #%s" % lot.id)
            
            display_name = " - ".join(name_parts)
            result.append((lot.id, display_name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Permite buscar por placa de inventario, número de serie o nombre del producto."""
        args = args or []
        domain = args[:]
        if name:
            # Buscar por placa de inventario (prioridad), número de serie o nombre del producto
            search_domain = [
                '|', '|',
                ('inventory_plate', operator, name),
                ('name', operator, name),
                ('product_id.name', operator, name)
            ]
            domain = search_domain + domain
        # Usar el método base con el dominio combinado
        return super(StockLot, self)._name_search(name, args=domain, operator=operator, limit=limit, order=order)

    def action_initialize_supply_lines(self):
            for lot in self:
                if lot.lot_supply_line_ids:
                    continue
                tmpl = lot.product_id.product_tmpl_id
                if not tmpl:
                    continue

                lines_to_create = []

                if getattr(tmpl, "is_composite", False):
                    for l in tmpl.composite_line_ids:
                        lines_to_create.append({
                            "lot_id": lot.id,
                            "item_type": "component",
                            "product_id": l.component_product_id.id,
                            "quantity": l.component_qty,
                            "uom_id": (l.component_uom_id or l.component_product_id.uom_id).id,
                        })

                if getattr(tmpl, "use_peripherals", False):
                    for l in tmpl.peripheral_line_ids:
                        lines_to_create.append({
                            "lot_id": lot.id,
                            "item_type": "peripheral",
                            "product_id": l.peripheral_product_id.id,
                            "quantity": l.peripheral_qty,
                            "uom_id": (l.peripheral_uom_id or l.peripheral_product_id.uom_id).id,
                        })

                if getattr(tmpl, "use_complements", False):
                    for l in tmpl.complement_line_ids:
                        lines_to_create.append({
                            "lot_id": lot.id,
                            "item_type": "complement",
                            "product_id": l.complement_product_id.id,
                            "quantity": l.complement_qty,
                            "uom_id": (l.complement_uom_id or l.complement_product_id.uom_id).id,
                        })

                if lines_to_create:
                    self.env["stock.lot.supply.line"].create(lines_to_create)

    def action_debug_view_info(self):
        """Método de debug para mostrar información de la vista y orden de campos."""
        from lxml import etree
        
        # Buscar todas las vistas del formulario para stock.lot (incluyendo heredadas)
        views = self.env['ir.ui.view'].search([
            ('model', '=', 'stock.lot'),
            ('type', '=', 'form'),
        ], order='priority desc, id desc')
        
        if not views:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pudo encontrar la vista.'),
                    'type': 'danger',
                }
            }
        
        # Obtener la vista completa combinada (Odoo combina las vistas heredadas)
        # Buscar la vista principal primero
        primary_view = views.filtered(lambda v: not v.inherit_id)
        if not primary_view:
            primary_view = views[0]
        
        # Obtener todas las vistas relacionadas (heredadas)
        all_views = [primary_view]
        inherit_views = views.filtered(lambda v: v.inherit_id)
        all_views.extend(inherit_views)
        
        # Obtener el archivo XML combinado usando el método de Odoo
        try:
            # Obtener la vista completa procesada por Odoo usando fields_view_get
            view_data = self.fields_view_get(view_id=primary_view.id, view_type='form')
            combined_arch = view_data.get('arch', '')
        except:
            try:
                # Intentar con get_combined_arch si está disponible
                combined_arch = primary_view.get_combined_arch()
            except:
                # Si falla, usar la vista principal
                combined_arch = primary_view.arch_db or primary_view.arch
        
        if not combined_arch:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pudo obtener la estructura de la vista.'),
                    'type': 'danger',
                }
            }
        
        # Parsear el XML
        try:
            if isinstance(combined_arch, bytes):
                root = etree.fromstring(combined_arch)
            else:
                root = etree.fromstring(combined_arch.encode('utf-8'))
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Error al parsear la estructura de la vista: %s') % str(e),
                    'type': 'danger',
                }
            }
        
        # Extraer información de las vistas
        view_names = []
        view_xml_ids = []
        for view in all_views:
            view_name = view.name or 'Sin nombre'
            view_xml_id = view.get_external_id().get(view.id, 'Sin XML ID')
            view_names.append(view_name)
            view_xml_ids.append(view_xml_id)
        
        # Recopilar todos los campos visibles en orden
        fields_info = []
        field_order = []
        
        def extract_fields(element, path='', level=0):
            """Función recursiva para extraer campos del XML."""
            for child in element:
                tag = child.tag
                if tag == 'field':
                    field_name = child.get('name', '')
                    if field_name:  # Solo procesar campos con nombre
                        field_string = child.get('string', field_name)
                        field_invisible = child.get('invisible', 'False')
                        field_readonly = child.get('readonly', 'False')
                        field_widget = child.get('widget', '')
                        
                        # Solo incluir campos visibles (no marcados como invisible)
                        is_invisible = field_invisible.lower() in ['1', 'true', 'True']
                        if not is_invisible:
                            field_order.append({
                                'name': field_name,
                                'string': field_string or field_name,
                                'path': path,
                                'level': level,
                                'readonly': field_readonly,
                                'widget': field_widget,
                            })
                            widget_text = f" [{field_widget}]" if field_widget else ""
                            fields_info.append(f"{len(field_order)}. {field_name} ({field_string or field_name}){widget_text}")
                
                # Continuar recursivamente (excluir algunos elementos que no son relevantes)
                if tag not in ['header', 'footer']:
                    child_path = f"{path}/{tag}" if path else tag
                    extract_fields(child, child_path, level + 1)
        
        # Extraer campos del formulario
        form_elements = root.xpath('//form')
        if form_elements:
            extract_fields(form_elements[0])
        else:
            # Si no hay form, buscar en el root
            extract_fields(root)
        
        # Construir el mensaje
        message_parts = [
            f"<strong>📋 Información de la Vista:</strong><br/>",
            f"<b>Vista Principal:</b> {view_names[0] if view_names else 'N/A'}<br/>",
            f"<b>XML ID Principal:</b> {view_xml_ids[0] if view_xml_ids else 'N/A'}<br/>",
            f"<b>Modelo:</b> {primary_view.model or 'N/A'}<br/>",
            f"<b>Tipo:</b> {primary_view.type or 'N/A'}<br/>",
            f"<b>Prioridad:</b> {primary_view.priority or 0}<br/>",
        ]
        
        if len(all_views) > 1:
            message_parts.append(f"<b>Vistas Heredadas:</b> {len(all_views) - 1}<br/>")
            for i, (name, xml_id) in enumerate(zip(view_names[1:], view_xml_ids[1:]), 1):
                message_parts.append(f"&nbsp;&nbsp;{i}. {name} ({xml_id})<br/>")
        
        message_parts.append(f"<br/><strong>📝 Orden de Campos ({len(field_order)} campos visibles):</strong><br/>")
        
        if fields_info:
            message_parts.append("<ol style='margin-left: 20px;'>")
            for info in fields_info:
                message_parts.append(f"<li style='margin-bottom: 5px;'>{info}</li>")
            message_parts.append("</ol>")
        else:
            message_parts.append("<p>No se encontraron campos visibles.</p>")
        
        # Agregar información detallada de cada campo
        if field_order:
            message_parts.append("<br/><strong>🔍 Detalles de Campos:</strong><br/>")
            message_parts.append("<ul style='margin-left: 20px;'>")
            for idx, field in enumerate(field_order, 1):
                readonly_text = " <span style='color: o