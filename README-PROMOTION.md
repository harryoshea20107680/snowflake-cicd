# Snowflake branch-based SQL promotion

**Current design:** `dev → qa → stage → main` corresponds to Snowflake databases `CC_PROJECT_DEV → CC_PROJECT_QA → CC_PROJECT_STAGE → CC_PROJECT_PROD`.

Developer changes originate inside Snowflake DEV and are extracted by `sync-dev.yml` into approved Git SQL files under `database/APP/`. Subsequent PRs promote **the same reviewed SQL definitions** to QA, STAGE and PROD; they do not re-extract target-environment DDL.

- The required GitHub PR check is named **`SQL Policy Check`** and includes promotion-order rules, unit tests and conservative SQL checks.
- `.github/workflows/deploy-environments.yml` deploys and verifies changed database SQL definitions when they land on `qa`, `stage` or `main`.
- `SNOWFLAKE_TARGET` selects the destination database (`QA`, `STAGE` or `PROD`).
- `scripts/promote_snapshots.py` provides validation/deployment, and `scripts/verify_deployment.py` provides target-specific verification.
- The AWS Lambda audit is enabled for QA, STAGE and PROD using branch-scoped AWS OIDC trust.

Review the full architecture and setup in [Multi-environment promotion](docs/MULTI-ENV-PROMOTION.md), and the smoke-test checks in [Deployment verification](docs/DEPLOYMENT-VERIFICATION.md).

**Limitations:** Table modifications need reviewed migrations. Snapshot deletion, missing/inaccessible objects and unsupported DDL fail closed. Existing objects may need reconciliation; dependency management, rollback and full functional testing are out of scope. GitHub branch rules must prevent direct pushes that bypass the PR check.
