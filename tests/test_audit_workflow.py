"""Static regression checks for deployment-to-AWS audit workflow contract."""
from pathlib import Path
import unittest

WORKFLOW = Path('.github/workflows/deploy-environments.yml')

class AuditWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKFLOW.read_text(encoding='utf-8')
        cls.audit = cls.content.split('  audit-deployment:\n', 1)[1]

    def test_audit_after_deployment_even_on_failure(self):
        self.assertIn('needs: deploy-environment', self.audit)
        self.assertIn('if: ${{ always() &&', self.audit)
        self.assertIn('DEPLOY_STATUS: ${{ needs.deploy-environment.result }}', self.audit)

    def test_all_environment_branches_are_targeted(self):
        for branch in ('qa', 'stage', 'main'):
            with self.subTest(branch=branch):
                self.assertIn("github.ref_name == '" + branch + "'", self.audit)

    def test_payload_environment_is_not_hardcoded(self):
        self.assertIn('AUDIT_ENV:', self.audit)
        self.assertIn('--arg environment "$AUDIT_ENV"', self.audit)
        self.assertIn('environment: $environment,', self.audit)
        self.assertNotIn('environment: "PROD",', self.audit)

    def test_existing_lambda_contract_preserved(self):
        for key in ('repository: $repo', 'run_id: $run',
                    'status: $status', 'object: $objects',
                    'verification:', '"failed_or_incomplete"',
                    'aws lambda invoke', '.logged == true'):
            with self.subTest(key=key):
                self.assertIn(key, self.audit)

if __name__ == '__main__':
    unittest.main()
