# Phase 1: QA post-deployment verification

The `deploy-qa.yml` workflow continues to deploy only approved, changed DEV
snapshot definitions. After promotion, it runs `scripts/verify_qa.py` with the
same previous-main commit SHA.

Checks:
- **Tables:** confirm exactly one matching `BASE TABLE` in QA metadata.
- **Views:** confirm exactly one matching `VIEW`, then run `SELECT * ... LIMIT 0`
  to verify query compilation without reading table rows.
- **Procedures:** confirm Snowflake metadata includes the matching overloaded
  argument signature (hashed using the same algorithm as `sync_dev.py`).
  Procedures are *not* executed because they may modify data.
- **No changed snapshots:** finish successfully without issuing Snowflake SQL.

Use `python3 -m unittest discover -s tests -v` for offline unit tests.
The `SQL Policy Check` PR workflow runs these tests automatically.

## End-to-end demonstration

1. Make a safe view change in `CC_PROJECT_DEV.APP`.
2. Manually run the DEV snapshot workflow from `main`.
3. Open a pull request for the generated snapshot branch and check that the
   required `SQL Policy Check` passes.
4. Review and merge the PR (this triggers automatic QA promotion).
5. Check `Deploy approved DEV snapshots to QA`: both deployment and
   `Verify promoted QA objects` steps should pass.
6. Independently query the changed object in QA and save logs/screenshots.

## Limitations

These smoke checks establish object existence and query compilation, **not**
functional correctness, data equivalence, or rollback. A verification failure
occurs *after* deployment and does not undo SQL already executed, so this is
not an atomic release or transaction. The existing fail-closed policy still
blocks modified tables, snapshot deletions and unsupported DDL; review changes
and use controlled remediation when a post-deployment check fails.
