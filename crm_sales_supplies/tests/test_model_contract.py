from odoo.tests.common import SavepointCase, tagged


@tagged("-at_install", "post_install")
class TestModelContract(SavepointCase):
    def test_purchase_order_extensions_exist(self):
        PurchaseOrder = self.env["purchase.order"]
        self.assertIn("approved_by_crm", PurchaseOrder._fields)
        self.assertIn("rejected_by_crm", PurchaseOrder._fields)
        self.assertIn("sale_order_ids", PurchaseOrder._fields)

    def test_sale_order_extensions_exist(self):
        SaleOrder = self.env["sale.order"]
        self.assertIn("purchase_alert_ids", SaleOrder._fields)
        self.assertIn("has_stock_issues", SaleOrder._fields)
