from odoo.tests.common import SavepointCase, tagged


@tagged("-at_install", "post_install")
class TestOperationPolicy(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case = cls.env["commercial.integration.case"].create({})
        cls.case.company_id = cls.env.company

    def test_policy_customer_only(self):
        self.env.company.integration_execution_policy = "customer_approved"
        self.assertTrue(self.case._can_execute_operations(proposal_ok=True, quote_ok=False))
        self.assertFalse(self.case._can_execute_operations(proposal_ok=False, quote_ok=True))

    def test_policy_quote_only(self):
        self.env.company.integration_execution_policy = "crm_quote_approved"
        self.assertFalse(self.case._can_execute_operations(proposal_ok=True, quote_ok=False))
        self.assertTrue(self.case._can_execute_operations(proposal_ok=False, quote_ok=True))

    def test_policy_either(self):
        self.env.company.integration_execution_policy = "either"
        self.assertTrue(self.case._can_execute_operations(proposal_ok=True, quote_ok=False))
        self.assertTrue(self.case._can_execute_operations(proposal_ok=False, quote_ok=True))
        self.assertFalse(self.case._can_execute_operations(proposal_ok=False, quote_ok=False))
