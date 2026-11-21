# Multi-environment Snowflake CI/CD proof of concept

## Environment and branch mapping

| Git branch | Snowflake database | How code reaches it |
|---|---|---|
| `dev` | `CC_PROJECT_DEV` | Edit directly in Snowflake DEV, run `sync-dev.yml` on `dev`, then merge generated snapshot PR into `dev` |
| `qa` | `CC_PROJECT_QA` | Approved `dev → qa` PR triggers deployment, verification and AWS audit |
| `stage` | `CC_PROJECT_STAGE` | Approved `qa → stage` PR triggers deployment, verification and AWS audit |
| `main` | `CC_PROJECT_PROD` | Approved `stage → main` PR triggers deployment, verification and AWS Lambda audit |

`dev-snapshots/` always contains **DEV-sourced** object definitions. QA/STAGE/PROD receive the same version-controlled DDL through reviewed PRs; they do not contribute replacement source snapshots. These are database environments, not separate geographic cloud regions.

## Controls

- GitHub ruleset `Snowflake Environment Branch Protection` targets all four environment branches. It requires a PR and passing **`SQL Policy Check`**, blocks force pushes, and prevents deletion. It currently requires **zero approving reviews**, so it does not guarantee independent sign-off.
- The PR workflow validates the route, tests the Python verifier and rejects unsupported or unsafe snapshot changes.
- `scripts/promote_snapshots.py` deploys changed, approved snapshots to `CC_PROJECT_QA`, `CC_PROJECT_STAGE` or `CC_PROJECT_PROD` according to `SNOWFLAKE_TARGET`.
- `scripts/verify_deployment.py` performs a non-destructive smoke verification of objects in that target environment.
- GitHub Actions authenticates to Snowflake via OIDC. The AWS auditing job uses AWS OIDC to invoke Lambda after QA, STAGE and PROD deployments. It is also scheduled after unsuccessful deployments, to record failed or incomplete outcomes. The IAM trust policy must explicitly allow all three branch subjects.

## Verified demonstration (21 November 2026)

1. [PR #21](https://github.com/harryoshea20107680/snowflake-cicd/pull/21) — captured `CICD_FULL_PIPELINE_V` from Snowflake DEV into `dev`.
2. [PR #22](https://github.com/harryoshea20107680/snowflake-cicd/pull/22) — promoted from `dev` to QA; deployment and verification passed.
3. [PR #23](https://github.com/harryoshea20107680/snowflake-cicd/pull/23) — promoted from `qa` to STAGE; deployment and verification passed.
4. [PR #24](https://github.com/harryoshea20107680/snowflake-cicd/pull/24) — promoted from `stage` to PROD; deployment, verification and AWS Lambda invocation passed.

The view is self-contained (`SELECT 1`), so it proves the promotion path without relying on un-reconciled historical tables. A successful workflow is not proof of full data parity or correctness in every environment.

## Limitations

- SQL validation is intentionally narrow; it is not a full parser or a production security review.
- Existing table modifications and snapshot removals require reviewed migrations. `--source-sync` permits changed-table definitions only during DEV-source review, not deployment.
- New tables cannot overwrite an existing target table. Other existing objects may need reconciliation.
- Procedures are verified by signature, not executed. Cross-object dependencies, grants, data migration, drift detection and rollback are not implemented.
- The branch ruleset currently has **zero required independent reviewers**. A required passing check alone is not independent approval.
- AWS/CloudWatch audit covers QA, STAGE and PROD after the AWS IAM trust policy is updated. Audit events report workflow outcomes, not an atomic database transaction or guaranteed rollback. Failed deployments may leave partial changes.
- Direct commits that bypass protected-branch PR checks would invalidate the route-control assumptions.

See [Deployment verification](DEPLOYMENT-VERIFICATION.md) and the [repository overview](../README.md).
