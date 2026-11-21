# Post-deployment verification: QA, STAGE and PROD

After `scripts/promote_snapshots.py --deploy` runs on an environment branch, `scripts/verify_deployment.py` independently verifies the approved changed `database/APP/` SQL definitions in the target selected by `SNOWFLAKE_TARGET`:

| Git branch | Target (`SNOWFLAKE_TARGET`) | Database |
|---|---|---|
| `qa` | `QA` | `CC_PROJECT_QA` |
| `stage` | `STAGE` | `CC_PROJECT_STAGE` |
| `main` | `PROD` | `CC_PROJECT_PROD` |

Both deployment and verification use the same previous **target-branch** commit SHA supplied by `github.event.before`.

## Checks

- **Tables:** metadata confirms exactly one matching base table in the target database.
- **Views:** metadata confirms exactly one matching view; a `SELECT * ... LIMIT 0` query checks compilation without fetching rows.
- **Procedures:** metadata must contain the same overloaded argument signature as the promoted snapshot; procedures are not executed, because they may change data.
- **No snapshot changes:** finishes successfully without issuing Snowflake SQL.

Successful output should include the actual target, for example:

```
VERIFIED VIEW: CC_PROJECT_STAGE.APP.CICD_FULL_PIPELINE_V
STAGE post-deployment verification PASSED (1 object(s)).
```

Run `python3 -m unittest discover -s tests -v` for offline tests. PRs run the same tests under the `SQL Policy Check` job.

## Demonstration

1. In Snowflake DEV, create or update an allowed self-contained SQL object.
2. Run `Sync Snowflake DEV definitions` on `dev` and merge its generated PR into `dev`.
3. Promote `dev → qa → stage → main`, checking each PR's SQL policy and each target's deployment workflow before proceeding.
4. Independently query the deployed objects in each Snowflake database using an authorised role.
5. After each QA, STAGE and PROD deployment, confirm its AWS Lambda audit event in CloudWatch.

## Limitations

Smoke checks prove existence and view compilation, not business correctness, data parity or rollback. A verification failure happens *after* SQL execution and cannot reverse prior statements. Unsupported DDL, snapshot deletions, and existing table migrations require manual review. Prior objects in the target are not automatically reconciled.
