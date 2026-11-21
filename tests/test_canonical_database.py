"""Offline regression checks for the canonical per-branch database/ design."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from check_promotion_path import changed_snapshots  # noqa: E402
from promote_snapshots import ROOT as SQL_ROOT, object_from_path  # noqa: E402
from sync_dev import DESTINATION  # noqa: E402


class CanonicalDatabaseTests(unittest.TestCase):
    def test_one_canonical_database_tree(self):
        self.assertEqual(SQL_ROOT, Path('database'))
        self.assertEqual(DESTINATION, Path('database'))
        self.assertTrue((ROOT / 'database/APP').is_dir())
        self.assertFalse((ROOT / 'dev-snapshots').exists())

    def test_canonical_sql_is_not_empty(self):
        self.assertGreater(len(list((ROOT / 'database/APP').rglob('*.sql'))), 0)
        self.assertTrue((ROOT / 'database/missing_or_inaccessible.txt').is_file())

    def test_dev_sync_is_restricted_to_dev_branch(self):
        workflow = (ROOT / '.github/workflows/sync-dev.yml').read_text()
        self.assertIn("if: github.ref == 'refs/heads/dev'", workflow)
        self.assertIn('git add -A database/', workflow)
        self.assertNotIn('git add -A dev-snapshots/', workflow)

    def test_deployment_and_audit_watch_canonical_directory(self):
        workflow = (ROOT / '.github/workflows/deploy-environments.yml').read_text()
        self.assertIn("- 'database/**'", workflow)
        self.assertIn('git diff --name-only', workflow)
        self.assertIn('-- database/ \\', workflow)
        self.assertNotIn('dev-snapshots/', workflow)

    def test_path_parser_accepts_canonical_app_sql(self):
        self.assertEqual(object_from_path(Path('database/APP/views/EXAMPLE_V.sql')),
                         ('APP', 'views', 'EXAMPLE_V'))
        self.assertEqual(object_from_path(Path('database/APP/tables/EXAMPLE_T.sql')),
                         ('APP', 'tables', 'EXAMPLE_T'))

    def test_path_parser_rejects_old_directory(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported snapshot file path'):
            object_from_path(Path('dev-snapshots/APP/views/EXAMPLE_V.sql'))

    def test_route_check_diffs_canonical_directory(self):
        output = subprocess.CompletedProcess(args=['git'], returncode=0,
                                             stdout='database/APP/views/EXAMPLE_V.sql\n', stderr='')
        with patch('check_promotion_path.subprocess.run', return_value=output) as run:
            self.assertTrue(changed_snapshots('a' * 40))
        command = run.call_args.args[0]
        self.assertEqual(command[-2:], ['--', 'database/'])

    def test_route_check_ignores_unmodified_canonical_sql(self):
        output = subprocess.CompletedProcess(args=['git'], returncode=0,stdout='',stderr='')
        with patch('check_promotion_path.subprocess.run', return_value=output):
            self.assertFalse(changed_snapshots('a' * 40))

    def test_required_sql_policy_name_is_stable(self):
        workflow = (ROOT / '.github/workflows/validate-sql.yml').read_text()
        self.assertIn('name: SQL Policy Check', workflow)


if __name__ == '__main__':
    unittest.main()
