#!/usr/bin/env python3
"""Capture visible DEV tables, views and procedures as review-only Git snapshots.

Requires Snowflake CLI OIDC configuration from snowflakedb/snowflake-actions.
Does not execute extracted DDL or remove files for missing objects.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

DATABASE = "CC_PROJECT_DEV"
ROLE = "GITHUB_CICD_ROLE"
WAREHOUSE = "CICD_WH"
DESTINATION = Path("dev-snapshots")

# Keep output paths predictable; fail on quoted/special names instead of skipping.
SIMPLE_NAME = re.compile(r"^[A-Z_][A-Z0-9_$]*$")

INVENTORY_SQL = f"""
SELECT TABLE_SCHEMA AS SCHEMA_NAME, TABLE_NAME AS OBJECT_NAME,
       CASE WHEN TABLE_TYPE = 'VIEW' THEN 'VIEW' ELSE 'TABLE' END AS OBJECT_TYPE,
       '' AS ARGUMENT_SIGNATURE
FROM {DATABASE}.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA'
  AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
UNION ALL
SELECT PROCEDURE_SCHEMA, PROCEDURE_NAME, 'PROCEDURE', ARGUMENT_SIGNATURE
FROM {DATABASE}.INFORMATION_SCHEMA.PROCEDURES
WHERE PROCEDURE_SCHEMA <> 'INFORMATION_SCHEMA'
ORDER BY SCHEMA_NAME, OBJECT_TYPE, OBJECT_NAME, ARGUMENT_SIGNATURE
"""


def query(sql: str) -> list[dict]:
    command = [
        "snow", "sql", "--database", DATABASE, "--warehouse", WAREHOUSE,
        "--role", ROLE, "--format", "JSON", "--silent",
        "--enhanced-exit-codes", "-x", "-q", sql,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError("Unexpected Snowflake CLI JSON response")
    return payload


def safe_name(value: str) -> str:
    if not isinstance(value, str) or not SIMPLE_NAME.fullmatch(value):
        raise ValueError(f"Unsupported quoted/special identifier: {value!r}")
    return value


def type_only_signature(signature: str | None) -> str:
    """Convert '(P_NAME VARCHAR, P_AMOUNT NUMBER(10,2))' to '(VARCHAR, NUMBER(10,2))'."""
    signature = (signature or "()").strip()
    if not (signature.startswith("(") and signature.endswith(")")):
        raise ValueError(f"Unexpected procedure signature: {signature}")
    body = signature[1:-1].strip()
    if not body:
        return "()"
    parts, start, depth = [], 0, 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(body[start:index].strip())
            start = index + 1
        if depth < 0:
            raise ValueError(f"Malformed procedure signature: {signature}")
    if depth:
        raise ValueError(f"Malformed procedure signature: {signature}")
    parts.append(body[start:].strip())
    data_types = []
    for part in parts:
        split = part.split(maxsplit=1)
        if len(split) != 2:
            raise ValueError(f"Cannot determine argument data type: {part}")
        data_types.append(split[1])
    return "(" + ", ".join(data_types) + ")"


def extract_snapshot(row: dict) -> tuple[Path, str]:
    schema = safe_name(row["SCHEMA_NAME"])
    name = safe_name(row["OBJECT_NAME"])
    kind = row["OBJECT_TYPE"]
    folders = {"TABLE": "tables", "VIEW": "views", "PROCEDURE": "procedures"}
    if kind not in folders:
        raise ValueError(f"Unsupported object type: {kind}")

    identifier = f'{DATABASE}."{schema}"."{name}"'
    output_stem = name
    if kind == "PROCEDURE":
        type_signature = type_only_signature(row["ARGUMENT_SIGNATURE"])
        identifier += type_signature
        # Signatures distinguish overloaded procedures without filename collision.
        short_id = hashlib.sha256(type_signature.encode()).hexdigest()[:10]
        output_stem = f"{name}__{short_id}"

    escaped_identifier = identifier.replace("'", "''")
    rows = query(f"SELECT GET_DDL('{kind}', '{escaped_identifier}', FALSE) AS DDL")
    if len(rows) != 1 or not isinstance(rows[0].get("DDL"), str):
        raise ValueError(f"Unexpected GET_DDL output for {identifier}")
    ddl = rows[0]["DDL"].strip()
    if not ddl or "#UNKNOWN_" in ddl.upper():
        raise ValueError(f"Unusable / incomplete DDL for {identifier}")
    return DESTINATION / schema / folders[kind] / f"{output_stem}.sql", ddl + "\n"


def main() -> None:
    inventory = query(INVENTORY_SQL)
    if not inventory:
        raise RuntimeError("No visible DEV objects. Refusing an empty snapshot.")

    expected: set[Path] = set()
    for object_row in inventory:
        file_path, contents = extract_snapshot(object_row)
        if file_path in expected:
            raise ValueError(f"Snapshot filename collision: {file_path}")
        expected.add(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists() or file_path.read_text(encoding="utf-8") != contents:
            file_path.write_text(contents, encoding="utf-8")
        print(f"Captured {object_row['OBJECT_TYPE']}: {file_path}")

    # These might have been deleted OR become invisible after a privilege change.
    # Preserve their files; never infer that removal in QA is safe.
    previous = set(DESTINATION.rglob("*.sql"))
    absent = sorted(previous - expected)
    report = DESTINATION / "missing_or_inaccessible.txt"
    report.write_text(
        "Missing from current DEV inventory (review manually; no automatic deletion):\n"
        + ("\n".join(str(p) for p in absent) if absent else "None") + "\n",
        encoding="utf-8",
    )
    print(f"Discovered {len(inventory)} visible objects; {len(absent)} missing/inaccessible candidates")


if __name__ == "__main__":
    main()
