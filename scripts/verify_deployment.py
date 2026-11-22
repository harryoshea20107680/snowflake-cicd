#!/usr/bin/env python3
# Called by: .github/workflows/deploy-environments.yml (post-deployment checks).
"""Non-destructively verify objects promoted by the approved DEV snapshot diff.

Run after promote_snapshots.py --deploy using the same previous target-branch base SHA.
These checks do not replace comprehensive data/integration tests or rollback.
"""

import argparse
import hashlib
import json
import subprocess
import sys

from promote_snapshots import Change, TARGET, TARGET_DB, collect, snow
from sync_dev import type_only_signature


def _verify_count(rows: list[dict], object_name: str) -> None:
    """Fail closed when an expected Snowflake metadata result is absent/ambiguous."""
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"{TARGET} verification returned invalid metadata for {object_name}")
    try:
        count = int(rows[0]["N"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{TARGET} verification returned invalid count for {object_name}") from exc
    if count != 1:
        raise ValueError(f"{TARGET} verification expected one matching object for {object_name}; found {count}")


def verify(changes: list[Change]) -> None:
    """Verify metadata for every promoted object; compile views without reading rows."""
    if not changes:
        print(f"{TARGET} verification: no changed snapshot definitions to check.")
        return

    for change in changes:
        qualified = f'{TARGET_DB}.{change.schema}.{change.name}'
        if change.folder in ("tables", "views"):
            table_type = "BASE TABLE" if change.folder == "tables" else "VIEW"
            rows = snow(
                f"SELECT COUNT(*) AS N FROM {TARGET_DB}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{change.schema}' "
                f"AND TABLE_NAME = '{change.name}' AND TABLE_TYPE = '{table_type}'",
                json_output=True,
            )
            _verify_count(rows, qualified)
            if change.folder == "views":
                # LIMIT 0 checks that references/privileges permit query compilation,
                # without scanning table data or executing stored procedures.
                snow(f'SELECT * FROM "{TARGET_DB}"."{change.schema}"."{change.name}" LIMIT 0')
            print(f"VERIFIED {table_type}: {qualified}")
        elif change.folder == "procedures":
            rows = snow(
                f"SELECT ARGUMENT_SIGNATURE FROM {TARGET_DB}.INFORMATION_SCHEMA.PROCEDURES "
                f"WHERE PROCEDURE_SCHEMA = '{change.schema}' AND PROCEDURE_NAME = '{change.name}'",
                json_output=True,
            )
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"{TARGET} verification could not find procedure {qualified}")
            expected_hash = change.path.stem.rsplit("__", 1)[-1]
            matches = 0
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"{TARGET} verification returned invalid procedure metadata for {qualified}")
                if not isinstance(row.get("ARGUMENT_SIGNATURE"), str):
                    raise ValueError(f"{TARGET} verification returned invalid procedure signature for {qualified}")
                signature = type_only_signature(row["ARGUMENT_SIGNATURE"])
                actual_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:10]
                matches += int(actual_hash == expected_hash)
            if matches != 1:
                raise ValueError(f"{TARGET} verification could not match the promoted procedure signature: {qualified}")
            print(f"VERIFIED PROCEDURE SIGNATURE: {qualified} ({expected_hash})")
        else:
            raise ValueError(f"Unsupported object type to verify: {change.folder}")

    print(f"{TARGET} post-deployment verification PASSED ({len(changes)} object(s)).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Previous target-branch commit SHA, identical to deployment step")
    args = parser.parse_args()
    verify(collect(args.base))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
