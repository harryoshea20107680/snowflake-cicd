"""Offline checks of the environment-branch promotion route policy."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_promotion_path import assert_promotion_path  # noqa: E402

REPO = "harryoshea20107680/snowflake-cicd"


class PromotionRouteTests(unittest.TestCase):
    def check(self, base: str, head: str, changed: bool = True, repo: str = REPO):
        assert_promotion_path(base, head, repo, REPO, changed)

    def test_dev_snapshot_branch_can_be_synced(self):
        self.check("dev", "sync/dev-all-123")

    def test_dev_to_qa(self):
        self.check("qa", "dev")

    def test_qa_to_stage(self):
        self.check("stage", "qa")

    def test_stage_to_prod(self):
        self.check("main", "stage")

    def test_skip_qa_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "required source is qa"):
            self.check("stage", "dev")

    def test_skip_stage_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "required source is stage"):
            self.check("main", "qa")

    def test_direct_snapshot_feature_to_prod_is_blocked(self):
        with self.assertRaises(ValueError):
            self.check("main", "feature/edit-sql")

    def test_snapshot_from_fork_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "same GitHub repository"):
            self.check("qa", "dev", repo="someone-else/snowflake-cicd")

    def test_infrastructure_change_to_main_is_allowed(self):
        self.check("main", "feature/workflow-change", changed=False)


if __name__ == "__main__":
    unittest.main()
