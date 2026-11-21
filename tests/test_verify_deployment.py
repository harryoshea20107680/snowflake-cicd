"""Offline tests for environment-specific verification; Snowflake CLI is mocked."""

import hashlib
import io
from contextlib import redirect_stdout
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from promote_snapshots import Change  # noqa: E402
from verify_deployment import verify  # noqa: E402
from sync_dev import type_only_signature  # noqa: E402


class VerificationTests(unittest.TestCase):
    @staticmethod
    def change(folder: str, name: str, filename: str | None = None) -> Change:
        return Change(
            status="A",
            path=Path(f"dev-snapshots/APP/{folder}/{filename or name + '.sql'}"),
            schema="APP",
            folder=folder,
            name=name,
            sql="CREATE OR REPLACE VIEW TEST_V AS SELECT 1;",
        )

    def test_view_exists_and_compiles_without_reading_rows(self) -> None:
        with patch("verify_deployment.snow", side_effect=[[{"N": 1}], "Statement executed"] ) as query:
            verify([self.change("views", "TEST_V")])
        self.assertEqual(query.call_count, 2)
        self.assertIn("TABLE_TYPE = 'VIEW'", query.call_args_list[0].args[0])
        self.assertTrue(query.call_args_list[0].kwargs["json_output"])
        self.assertEqual(query.call_args_list[1].args[0],
                         'SELECT * FROM "CC_PROJECT_QA"."APP"."TEST_V" LIMIT 0')

    def test_missing_view_fails_without_compiling(self) -> None:
        with patch("verify_deployment.snow", return_value=[{"N": 0}]) as query:
            with self.assertRaisesRegex(ValueError, "expected one matching object"):
                verify([self.change("views", "TEST_V")])
        query.assert_called_once()

    def test_added_table_checked_as_base_table(self) -> None:
        with patch("verify_deployment.snow", return_value=[{"N": 1}]) as query:
            verify([self.change("tables", "TEST_T")])
        query.assert_called_once()
        self.assertIn("TABLE_TYPE = 'BASE TABLE'", query.call_args.args[0])

    def test_procedure_exact_signature_hash(self) -> None:
        signature = "(P_AMOUNT NUMBER(10,2))"
        suffix = hashlib.sha256(type_only_signature(signature).encode()).hexdigest()[:10]
        c = self.change("procedures", "TEST_PROC", f"TEST_PROC__{suffix}.sql")
        with patch("verify_deployment.snow", return_value=[{"ARGUMENT_SIGNATURE": signature}]) as query:
            verify([c])
        query.assert_called_once()
        self.assertIn("INFORMATION_SCHEMA.PROCEDURES", query.call_args.args[0])

    def test_non_matching_procedure_signature_fails(self) -> None:
        c = self.change("procedures", "TEST_PROC", "TEST_PROC__0000000000.sql")
        with patch("verify_deployment.snow", return_value=[{"ARGUMENT_SIGNATURE": "(P_AMOUNT NUMBER(10,2))"}]):
            with self.assertRaisesRegex(ValueError, "could not match"):
                verify([c])

    def test_no_changes_does_not_query_snowflake(self) -> None:
        with patch("verify_deployment.snow") as query:
            verify([])
        query.assert_not_called()

    def test_malformed_metadata_fails_closed(self) -> None:
        with patch("verify_deployment.snow", return_value=[{"WRONG_KEY": 1}]):
            with self.assertRaisesRegex(ValueError, "invalid count"):
                verify([self.change("tables", "TEST_T")])


    def test_stage_no_change_message_has_correct_target(self) -> None:
        output = io.StringIO()
        with patch("verify_deployment.TARGET", "STAGE"), redirect_stdout(output):
            verify([])
        self.assertIn("STAGE verification: no changed snapshot definitions", output.getvalue())
        self.assertNotIn("QA verification", output.getvalue())

    def test_prod_success_message_has_correct_target(self) -> None:
        output = io.StringIO()
        with (
            patch("verify_deployment.TARGET", "PROD"),
            patch("verify_deployment.snow", return_value=[{"N": 1}]),
            redirect_stdout(output),
        ):
            verify([self.change("tables", "TEST_T")])
        self.assertIn("PROD post-deployment verification PASSED", output.getvalue())
        self.assertNotIn("QA post-deployment verification PASSED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
