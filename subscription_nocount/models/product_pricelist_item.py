from odoo import api, fields, models


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    @api.depends("plan_id")
    def _compute_price_label(self):
        """
        Mantener el comportamiento estándar y, SOLO para reglas recurrentes en USD,
        mostrar siempre el precio con dos decimales y coma (12,50) en la etiqueta.
        Las reglas en COP quedan intactas.
        """
        # 1) Lógica original (incluye enterprise sale_subscription)
        super(ProductPricelistItem, self)._compute_price_label()

        # 2) Ajuste específico para USD/COP (resto queda como Odoo)
        for item in self:
            if not (item.plan_id and item.compute_price in ("fixed", "percentage")):
                continue

            # Determinar moneda de la regla recurrente
            currency = getattr(item, "currency_id", False) or getattr(
                item.pricelist_id, "currency_id", False
            )
            if not currency or currency.name not in ("USD", "COP"):
                # Para otras monedas, dejamos el label tal como lo dejó Odoo.
                continue

            # Usar fixed_price cuando es precio fijo, que es numérico y está en USD.
            price_details = None
            if item.compute_price == "fixed" and "fixed_price" in item._fields:
                price_details = item.fixed_price
            else:
                price_details = item.price

            try:
                price_num = float(price_details)
                if currency.name == "USD":
                    # Formato 2 decimales y coma como separador: 12,50
                    price_str = f"{price_num:.2f}".replace(".", ",")
                else:
                    # COP: sin decimales, miles con punto, ej: 12.000
                    price_str = "{:,.0f}".format(price_num).replace(",", ".")
            except (TypeError, ValueError):
                price_str = price_details

            # Anteponer símbolo de la moneda (ej. "$ 12,50" / "$ 12.000")
            symbol = getattr(currency, "symbol", "") or currency.name or ""
            # Añadir código de moneda al final: "USD" / "COP"
            price_label = f"{symbol} {price_str} {currency.name}".strip()

            item.price = item.env._(
                "%(price_details)s %(recurrence)s",
                price_details=price_label,
                recurrence=item.plan_id.sudo().billing_period_display_sentence,
            )

