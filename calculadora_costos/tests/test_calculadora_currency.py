from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase, tagged


def _fake_convert(self, amount, source_currency, target_currency, date=None):
    source_name = getattr(source_currency, "name", "")
    target_name = getattr(target_currency, "name", "")
    if source_name == target_name:
        return amount
    if source_name == "USD" and target_name == "COP":
        return amount * 4000.0
    if source_name == "COP" and target_name == "USD":
        return amount / 4000.0
    return amount


@tagged("-at_install", "post_install")
class TestCalculadoraCurrency(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Calculadora"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Equipo Demo",
                "type": "consu",
                "list_price": 100.0,
            }
        )
        cls.usd = cls.env.ref("base.USD")
        cls.cop = cls.env.ref("base.COP")

    def _create_calc(self, **extra_vals):
        vals = {
            "name": "Calc Demo",
            "partner_id": self.partner.id,
            "currency_id": self.usd.id,
            "rate_date": "2026-04-16",
            "tipo_operacion": "venta",
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": self.product.display_name,
                        "product_qty": 2.0,
                        "price_unit": 100.0,
                        "moneda_equipo": "USD",
                    },
                )
            ],
        }
        vals.update(extra_vals)
        return self.env["calculadora.costos"].create(vals)

    def test_sale_totals_with_usd_quote_currency(self):
        with patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._get_applied_rate", lambda self, source_currency=None, target_currency=None, date=None: 4000.0), patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._convert_currency_amount", _fake_convert):
            calc = self._create_calc()
            calc._compute_applied_currency_rate()
            calc.line_ids._compute_bases_cop()
            calc._compute_agregados_desde_lineas()
            calc._compute_costo_con_utilidad()
            calc._compute_costo_equipo_cop()
            calc._compute_costo_total_cop()
            calc._compute_pago_mensual()
            calc._compute_total_pagar()
            calc._compute_quote_amounts()

        self.assertEqual(calc.calculation_type, "sale")
        self.assertEqual(calc.applied_currency_rate, 4000.0)
        self.assertAlmostEqual(calc.costo_equipo_cop, 880000.0)
        self.assertAlmostEqual(calc.quote_equipment_total, 220.0)
        self.assertEqual(calc.quote_monthly_amount, 0.0)

    def test_subscription_totals_include_services(self):
        with patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._get_applied_rate", lambda self, source_currency=None, target_currency=None, date=None: 4000.0), patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._convert_currency_amount", _fake_convert):
            calc = self._create_calc(
                tipo_operacion="suscripcion",
                plazo_meses="12",
                costo_servicio_tecnico_mensual_cop=100000.0,
                porcentaje_margen_servicio=15.0,
            )
            calc._compute_applied_currency_rate()
            calc.line_ids._compute_bases_cop()
            calc._compute_agregados_desde_lineas()
            calc._compute_costo_con_utilidad()
            calc._compute_costo_equipo_cop()
            calc._compute_costo_total_cop()
            calc._compute_servicio_con_margen()
            calc._compute_total_servicio_tecnico_plazo_cop()
            calc._compute_pago_mensual()
            calc._compute_total_pagar()
            calc._compute_quote_amounts()

        self.assertEqual(calc.calculation_type, "subscription")
        self.assertGreater(calc.pago_mensual, 0.0)
        self.assertGreater(calc.total_pagar, calc.costo_equipo_cop)
        self.assertGreater(calc.quote_monthly_amount, 0.0)

    def test_missing_rate_is_blocked(self):
        calc = self._create_calc()
        with patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._get_applied_rate", lambda self, source_currency=None, target_currency=None, date=None: 0.0):
            calc._compute_applied_currency_rate()
        with self.assertRaises(ValidationError):
            calc._check_quote_rate()
