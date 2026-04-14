# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CalculadoraCostosLine(models.Model):
    _name = "calculadora.costos.line"
    _description = "Línea de equipo (producto, cantidad, precio y moneda)"
    _order = "sequence, id"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "calculadora_id" in fields_list and not res.get("calculadora_id"):
            cid = self.env.context.get("default_calculadora_id")
            if cid:
                res["calculadora_id"] = cid
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("calculadora_id"):
                cid = self.env.context.get("default_calculadora_id")
                if cid:
                    vals["calculadora_id"] = cid
        return super().create(vals_list)

    calculadora_id = fields.Many2one(
        "calculadora.costos",
        string="Calculadora",
        required=False,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Nº", default=10)
    name = fields.Char(string="Descripción")

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        index=True,
        help="Producto de catálogo; al elegirlo se cargan nombre, precio de lista y moneda.",
    )
    product_qty = fields.Float(
        string="Cantidad",
        default=1.0,
        required=True,
        digits=(16, 3),
        help="Cantidad de unidades del producto en esta línea.",
    )
    price_unit = fields.Float(
        string="Precio unitario",
        digits=(16, 4),
        default=0.0,
        help="Precio unitario en la moneda indicada (no en COP; la conversión a COP usa la TRM de la cotización).",
    )

    moneda_equipo = fields.Selection(
        [("USD", "USD"), ("COP", "COP")],
        string="Moneda precio",
        default="USD",
        required=True,
        help="Moneda del precio unitario y de la garantía en esta línea.",
    )

    product_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda producto (ref.)",
        readonly=True,
        help="Moneda de referencia del producto al cargarlo desde catálogo (solo informativo).",
    )

    line_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        compute="_compute_line_currency_id",
        store=False,
    )

    monto_garantia = fields.Float(
        string="Valor garantía",
        digits=(16, 2),
        default=0.0,
        help="Importe de garantía en la misma moneda que el precio del equipo (USD o COP).",
    )

    # Bases en COP sin utilidad (una sola conversión TRM si la línea está en USD)
    equipo_base_cop = fields.Float(
        string="Equipo base (COP)",
        compute="_compute_bases_cop",
        store=True,
        digits=(16, 2),
        help="(Cantidad × precio unitario) convertido a COP sin aplicar utilidad.",
    )
    garantia_base_cop = fields.Float(
        string="Garantía base (COP)",
        compute="_compute_bases_cop",
        store=True,
        digits=(16, 2),
        help="Garantía convertida a COP sin aplicar utilidad.",
    )
    subtotal_base_cop = fields.Float(
        string="Subtotal línea (COP)",
        compute="_compute_bases_cop",
        store=True,
        digits=(16, 2),
        help="Suma de bases COP de la línea (equipo + garantía), sin utilidad.",
    )

    currency_id = fields.Many2one(
        related="calculadora_id.currency_id",
        string="Moneda cotización",
        readonly=True,
    )

    @api.depends("moneda_equipo")
    def _compute_line_currency_id(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        cop = self.env.ref("base.COP", raise_if_not_found=False)
        for line in self:
            if line.moneda_equipo == "USD" and usd:
                line.line_currency_id = usd
            elif cop:
                line.line_currency_id = cop
            else:
                line.line_currency_id = False

    def amount_equipment(self):
        """Importe total del equipo en moneda de línea (sin garantía): cantidad × precio."""
        self.ensure_one()
        return (self.product_qty or 0.0) * (self.price_unit or 0.0)

    @api.depends(
        "moneda_equipo",
        "product_qty",
        "price_unit",
        "monto_garantia",
        "calculadora_id.trm",
    )
    def _compute_bases_cop(self):
        for line in self:
            if not line.calculadora_id:
                line.equipo_base_cop = 0.0
                line.garantia_base_cop = 0.0
                line.subtotal_base_cop = 0.0
                continue
            trm = line.calculadora_id.trm or 4000.0
            if trm <= 0:
                trm = 4000.0
            amt = line.amount_equipment()
            if line.moneda_equipo == "USD":
                line.equipo_base_cop = amt * trm
                line.garantia_base_cop = (line.monto_garantia or 0.0) * trm
            else:
                line.equipo_base_cop = amt
                line.garantia_base_cop = line.monto_garantia or 0.0
            line.subtotal_base_cop = line.equipo_base_cop + line.garantia_base_cop

    def _product_price_currency(self, product):
        """Moneda en la que está expresado el precio de lista del producto."""
        tmpl = product.product_tmpl_id
        cur = getattr(tmpl, "currency_id", None) or getattr(product, "currency_id", None)
        if not cur:
            cur = product.company_id.currency_id or self.env.company.currency_id
        return cur

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            self.product_currency_id = False
            return
        product = self.product_id
        price = product.lst_price
        cur = self._product_price_currency(product)
        self.product_currency_id = cur
        self.name = product.display_name
        company = self.env.company
        date = fields.Date.context_today(self)
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        cop = self.env.ref("base.COP", raise_if_not_found=False)

        if usd and cur and cur.id == usd.id:
            self.moneda_equipo = "USD"
            self.price_unit = price
        elif cop and cur and cur.id == cop.id:
            self.moneda_equipo = "COP"
            self.price_unit = price
        else:
            # Otra moneda del producto: expresar precio en COP (una conversión)
            self.moneda_equipo = "COP"
            if cur and cop:
                self.price_unit = cur._convert(price, cop, company, date)
            else:
                self.price_unit = price
        if not self.product_qty:
            self.product_qty = 1.0

    @api.constrains("calculadora_id")
    def _check_calculadora_id(self):
        for line in self:
            if not line.calculadora_id:
                raise ValidationError(
                    _(
                        "Cada línea de equipo debe estar vinculada a una cotización. "
                        "Use la pestaña «Costos del Equipo» o guarde la cabecera antes de añadir líneas."
                    )
                )

    @api.constrains("product_qty")
    def _check_product_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que cero."))
