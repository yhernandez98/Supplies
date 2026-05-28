from unittest.mock import patch

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
class TestBridgeSync(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Cliente Bridge"})
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor Bridge", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop Bridge",
                "type": "consu",
            }
        )
        cls.usd = cls.env.ref("base.USD")
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)

    def _create_purchase_order(self):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "currency_id": self.usd.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.display_name,
                            "product_id": self.product.id,
                            "product_qty": 1.0,
                            "product_uom": self.product.uom_po_id.id or self.product.uom_id.id,
                            "price_unit": 250.0,
                            "date_planned": "2026-04-16 00:00:00",
                        },
                    )
                ],
            }
        )

    def test_sync_from_purchase_order_preserves_quote_currency(self):
        po = self._create_purchase_order()
        case = self.env["commercial.integration.case"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        with patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._get_applied_rate", lambda self, source_currency=None, target_currency=None, date=None: 4000.0), patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._convert_currency_amount", _fake_convert):
            calc = case._sync_calculadora_from_po(po)
            calc._compute_applied_currency_rate()
            calc.line_ids._compute_bases_cop()
            calc._compute_agregados_desde_lineas()
            calc._compute_costo_con_utilidad()
            calc._compute_costo_equipo_cop()
            calc._compute_costo_total_cop()
            calc._compute_quote_amounts()

        self.assertEqual(calc.currency_id, self.usd)
        self.assertEqual(calc.calculation_type, "sale")
        self.assertEqual(calc.line_ids[:1].moneda_equipo, "USD")
        self.assertEqual(calc.applied_currency_rate, 4000.0)

    def test_snapshot_uses_quote_currency_and_rate(self):
        po = self._create_purchase_order()
        case = self.env["commercial.integration.case"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        with patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._get_applied_rate", lambda self, source_currency=None, target_currency=None, date=None: 4000.0), patch("odoo.addons.calculadora_costos.models.calculadora.Calculadora._convert_currency_amount", _fake_convert):
            calc = case._sync_calculadora_from_po(po)
            calc._compute_applied_currency_rate()
            calc.line_ids._compute_bases_cop()
            calc._compute_agregados_desde_lineas()
            calc._compute_costo_con_utilidad()
            calc._compute_costo_equipo_cop()
            calc._compute_costo_total_cop()
            calc.bridge_apply_tax = True
            calc._compute_bridge_pricing()
            proposal = self.env["commercial.customer.proposal"].create({"case_id": case.id})
            proposal._snapshot_from_calculadora(calc)

        self.assertEqual(proposal.currency_id, self.usd)
        self.assertEqual(proposal.applied_currency_rate, 4000.0)
        self.assertGreater(proposal.snap_total_customer_cop, 0.0)
