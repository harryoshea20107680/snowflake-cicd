# CI/CD architecture

This project separates four Snowflake databases using Git branches: `dev` (DEV), `qa` (QA), `stage` (STAGE) and `main` (PROD).

## Promotion flow

1. **Snowflake DEV → Git `dev`:** `sync-dev.yml` extracts the visible SQL object definitions with `GET_DDL` and prepares a review branch.
2. **`dev → qa → stage → main`:** pull requests carry the same SQL files under `database/APP/` through the environments. QA, STAGE and PROD are not used as DDL sources.
3. **Validation:** `validate-sql.yml` runs the required `SQL Policy Check`, including promotion-order rules, SQL restrictions and unit tests.
4. **Deployment:** `deploy-environments.yml` deploys changed objects on merges into `qa`, `stage` or `main`, then verifies them in the corresponding Snowflake database.
5. **Audit:** the deployment workflow authenticates to AWS via OIDC and invokes Lambda to record the environment, run ID and deployment outcome in CloudWatch.

## Security and constraints

- GitHub branch protection requires PRs and a passing policy check on all four environment branches. No independent approving review is currently required.
- Snowflake authentication uses OIDC rather than stored user passwords. AWS audit invocation also uses OIDC.
- The SQL policy blocks unsupported or unsafe changes. Existing-table modifications and object deletions are not automatically deployed.
- The pipeline does not include automatic rollback, full drift detection or database-wide data reconciliation.

## Completed demonstration

The self-contained view `CICD_CANONICAL_DATABASE_V` passed through [DEV capture (PR #46)](https://github.com/harryoshea20107680/snowflake-cicd/pull/46), [QA (PR #47)](https://github.com/harryoshea20107680/snowflake-cicd/pull/47), [STAGE (PR #48)](https://github.com/harryoshea20107680/snowflake-cicd/pull/48) and [PROD (PR #49)](https://github.com/harryoshea20107680/snowflake-cicd/pull/49). All three deployment and AWS Lambda audit jobs reported success.
