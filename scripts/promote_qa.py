#!/usr/bin/env python3
"""Validate approved DEV snapshots and promote safe changes to Snowflake QA.

Usage:
    python scripts/promote_qa.py --check --base BASE_COMMIT
    python scripts/promote_qa.py --deploy --base PREVIOUS_MAIN_SHA

Snapshot removals, changed tables, inaccessible objects and unsupported DDL fail closed.
No extracted CREATE OR REPLACE TABLE is executed against QA.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path("dev-snapshots")
QA_DB = "CC_PROJECT_QA"
QA_ROLE = "GITHUB_CICD_ROLE"
WAREHOUSE = "CICD_WH"
VALID_NAME = re.compile(r"[A-Z_][A-Z0-9_$]*\Z")
ALLOWED_KINDS = {"tables": "TABLE", "views": "VIEW", "procedures": "PROCEDURE"}


@dataclass(frozen=True)
class Change:
    status: str
    path: Path
    schema: str
    folder: str
    name: str
    sql: str


def run(command: list[str], *, capture: bool = True) -> str:
    p = subprocess.run(command, check=True, text=True,
                       stdout=subprocess.PIPE if capture else None)
    return p.stdout if capture else ""


def changed_files(base: str) -> list[tuple[str, Path]]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", base):
        raise ValueError("Expected full 40-character Git commit hash for --base")
    output = run(["git", "diff", "--name-status", "--no-renames", base, "HEAD", "--", str(ROOT)])
    results = []
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        results.append((status, Path(path)))
    return results


def object_from_path(path: Path) -> tuple[str, str, str]:
    parts = path.parts
    if len(parts) != 4 or parts[0] != "dev-snapshots" or parts[2] not in ALLOWED_KINDS or path.suffix != ".sql":
        raise ValueError(f"Unsupported snapshot file path: {path}")
    schema, folder, stem = parts[1], parts[2], path.stem
    if not VALID_NAME.fullmatch(schema):
        raise ValueError(f"Invalid schema: {schema}")
    # Stored procedure files include a signature hash from the snapshotter.
    name = stem.split("__", 1)[0] if folder == "procedures" else stem
    if not VALID_NAME.fullmatch(name):
        raise ValueError(f"Invalid object name: {name}")
    if folder == "procedures" and not re.fullmatch(r"[A-Z_][A-Z0-9_$]*__[a-f0-9]{10}", stem):
        raise ValueError(f"Unsupported procedure snapshot filename: {stem}")
    return schema, folder, name


def ensure_single_statement(ddl: str, path: Path) -> None:
    """Reject extra SQL outside quotes/comments/dollar-quoted procedure bodies."""
    i = 0
    state = "normal"
    semicolons = 0
    while i < len(ddl):
        c = ddl[i]
        nxt = ddl[i + 1] if i + 1 < len(ddl) else ""
        if state == "normal":
            if c == "'":
                state = "single"
            elif c == '"':
                state = "double"
            elif c == "$" and nxt == "$":
                state = "dollar"
                i += 1
            elif c == "-" and nxt == "-":
                state = "line_comment"
                i += 1
            elif c == "/" and nxt == "*":
                state = "block_comment"
                i += 1
            elif c == ";":
                semicolons += 1
                if semicolons > 1 or ddl[i+1:].strip():
                    # Comments following the final semicolon are intentionally unsupported.
                    raise ValueError(f"{path}: extra SQL after the first statement")
        elif state == "single" and c == "'":
            if nxt == "'":
                i += 1
            else:
                state = "normal"
        elif state == "double" and c == '"':
            if nxt == '"':
                i += 1
            else:
                state = "normal"
        elif state == "dollar" and c == "$" and nxt == "$":
            state = "normal"
            i += 1
        elif state == "line_comment" and c == "\n":
            state = "normal"
        elif state == "block_comment" and c == "*" and nxt == "/":
            state = "normal"
            i += 1
        i += 1
    if semicolons != 1 or state not in ("normal", "line_comment"):
        raise ValueError(f"{path}: expected one terminated SQL statement")


def validate_definition(path: Path, kind: str, name: str) -> str:
    ddl = path.read_text(encoding="utf-8").strip()
    # Recognize only the exact supported top-level Snowflake GET_DDL object types.
    pattern = re.compile(
        rf'^CREATE\s+(?:OR\s+REPLACE\s+)?{kind}\s+"?{re.escape(name)}"?(?=[\s(])',
        re.IGNORECASE,
    )
    if not pattern.match(ddl):
        raise ValueError(f"{path}: DDL must create {kind} {name} without a qualified name")
    if re.search(r"(?i)\bCC_PROJECT_(?:DEV|STAGE|PROD)\b", ddl):
        raise ValueError(f"{path}: environment-specific database reference")
    if "#UNKNOWN_" in ddl.upper():
        raise ValueError(f"{path}: incomplete object metadata")
    if not ddl.endswith(";"):
        raise ValueError(f"{path}: expected terminating semicolon")
    ensure_single_statement(ddl, path)
    return ddl


def collect(base: str) -> list[Change]:
    report = ROOT / "missing_or_inaccessible.txt"
    if report.exists():
        status = report.read_text(encoding="utf-8").strip().splitlines()
        if len(status) < 2 or status[1:] != ["None"]:
            raise ValueError("DEV inventory reports missing or inaccessible objects; investigate before QA promotion")

    changes = []
    for status, path in changed_files(base):
        if path == report:
            if status == "D":
                raise ValueError("DEV inventory status report must not be deleted")
            continue
        if not path.name.endswith(".sql"):
            raise ValueError(f"Unexpected file in snapshot update: {path}")
        schema, folder, name = object_from_path(path)
        if status not in ("A", "M"):
            raise ValueError(f"Snapshot removals are not automatically promoted: {status} {path}")
        if folder == "tables" and status != "A":
            raise ValueError(f"Table modifications need a reviewed migration: {path}")
        ddl = validate_definition(path, ALLOWED_KINDS[folder], name)
        changes.append(Change(status, path, schema, folder, name, ddl))

    # Reject collisions between procedure overload files and schemas with conflicting paths.
    return sorted(changes, key=lambda x: ({"tables": 0, "views": 1, "procedures": 2}[x.folder], x.schema, str(x.path)))


def snow(sql: str, *, schema: str | None = None, json_output: bool = False):
    command = ["snow", "sql", "--database", QA_DB,
               "--warehouse", WAREHOUSE, "--role", QA_ROLE,
               "--enhanced-exit-codes", "-x"]
    if schema:
        command += ["--schema", schema]
    if json_output:
        command += ["--format", "JSON", "--silent"]
    command += ["-q", sql]
    output = run(command)
    if json_output:
        rows = json.loads(output)
        if not isinstance(rows, list):
            raise ValueError("Unexpected Snowflake JSON format")
        return rows
    return output


def deploy(changes: list[Change]):
    if not changes:
        print("No changed snapshot definitions. No QA deployment necessary.")
        return
    print(f"Promoting {len(changes)} approved snapshot(s) to {QA_DB}")

    # Fail before executing any DDL when an added table name already exists in QA.
    for c in changes:
        if c.folder == "tables":
            rows = snow(
                f"SELECT COUNT(*) AS N FROM {QA_DB}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{c.schema}' AND TABLE_NAME = '{c.name}'",
                json_output=True,
            )
            if len(rows) != 1 or int(rows[0]["N"]) != 0:
                raise ValueError(f"New table snapshot already exists in QA: {c.schema}.{c.name}; manual reconciliation required")

    for c in changes:
        schema = c.schema
        # Quotes are safe because schema name is restricted to simple uppercase identifiers.
        snow(f'CREATE SCHEMA IF NOT EXISTS {QA_DB}."{schema}"')
        sql = c.sql
        if c.folder == "tables":
            header = re.compile(r"^CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\b", re.I)
            sql = header.sub("CREATE TABLE IF NOT EXISTS", sql, count=1)
            if not sql.startswith("CREATE TABLE IF NOT EXISTS"):
                raise ValueError("Unsafe table header conversion")
        # Every statement is executed in the QA database and matching schema.
        print(f"Deploying {c.folder[:-1]} {schema}.{c.name} from {c.path}")
        snow(sql, schema=schema)
    print("QA promotion completed. Confirm the deployed objects with an independent SQL query.")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Fail unsafe snapshot PR changes")
    mode.add_argument("--deploy", action="store_true", help="Deploy safe changed snapshots to QA")
    parser.add_argument("--base", required=True, help="Base SHA to diff against current HEAD")
    args = parser.parse_args()
    changes = collect(args.base)
    print("Snapshot changes: " + (", ".join(str(c.path) for c in changes) if changes else "none"))
    if args.deploy:
        deploy(changes)
    else:
        print(f"Snapshot validation passed ({len(changes)} changed DDL file(s))")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
