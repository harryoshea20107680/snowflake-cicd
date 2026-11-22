# Deployment verification and audit

Following deployment to QA, STAGE or PROD, `scripts/verify_deployment.py` checks the objects changed in the approved Git commit.

## Verification performed

- **Tables:** confirm exactly one matching base table exists.
- **Views:** confirm the view exists and compile a `SELECT * ... LIMIT 0` query without retrieving data.
- **Procedures:** confirm the expected procedure argument signature without executing the procedure.
- **No SQL changes:** no database object verification is needed.

The target databases are `CC_PROJECT_QA`, `CC_PROJECT_STAGE` and `CC_PROJECT_PROD`.

## Evidence from the final test

| Environment | Verified workflow | Result |
|---|---|---|
| QA | [Run #45038206116](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45038206116) | View verified; Lambda returned `logged: true` |
| STAGE | [Run #45038636180](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45038636180) | View verified; Lambda returned `logged: true` |
| PROD | [Run #45039057826](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45039057826) | View verified; Lambda returned `logged: true` |

These results confirm successful GitHub Actions deployments, Snowflake smoke verification and Lambda logging acknowledgements. A separate CloudWatch log inspection can provide additional audit evidence.

**Limitation:** Smoke checks do not prove business correctness or data parity. SQL execution is not atomic across an entire promotion, and failed deployments are not automatically rolled back.
