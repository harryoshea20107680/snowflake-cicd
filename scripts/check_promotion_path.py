#!/usr/bin/env python3
# Called by: .github/workflows/validate-sql.yml (PR promotion-order check).
"""Enforce sequential PR promotion of database SQL through environment branches.

Infrastructure-only PRs without database/ changes remain permissible.
Branch protection must separately prevent direct pushes to QA, STAGE and main.
"""

import argparse
import re
import subprocess
import sys

EXPECTED_SOURCE = {"qa": "dev", "stage": "qa", "main": "stage"}
VALID_TARGETS = frozenset({"dev", *EXPECTED_SOURCE})


def assert_promotion_path(
    base_branch: str,
    head_branch: str,
    head_repo: str,
    repository: str,
    snapshot_changed: bool,
) -> None:
    if base_branch not in VALID_TARGETS:
        raise ValueError(f"Unknown environment branch: {base_branch}")
    if not snapshot_changed:
        print("No database SQL changes; promotion source restriction not applicable.")
        return
    if head_repo != repository:
        raise ValueError("SQL snapshot promotion must originate in the same GitHub repository")
    required = EXPECTED_SOURCE.get(base_branch)
    if required and head_branch != required:
        raise ValueError(
            f"Invalid SQL promotion: {head_branch} -> {base_branch}; "
            f"required source is {required}"
        )
    print(f"APPROVED PR route: {head_branch} -> {base_branch}")


def changed_snapshots(base_sha: str) -> bool:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", base_sha):
        raise ValueError("Expected full Git base commit SHA")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", base_sha, "HEAD", "--", "database/"],
        check=True,
        text=True,
        capture_output=True,
    )
    return bool(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--head-branch", required=True)
    parser.add_argument("--head-repo", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    assert_promotion_path(args.base_branch, args.head_branch, args.head_repo,
                          args.repository, changed_snapshots(args.base_sha))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
