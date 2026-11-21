# Snowflake CI/CD — DEV → QA → STAGE → PROD

A cloud-native CI/CD proof of concept using **Snowflake**, **GitHub Actions**, **GitHub OIDC** and **AWS Lambda/CloudWatch**.

## Environment mapping

| Git branch | Snowflake environment | Purpose |
|---|---|---|
| `dev` | `CC_PROJECT_DEV` | Developers edit objects in DEV; `sync-dev.yml` captures definitions for review in Git |
| `qa` | `CC_PROJECT_QA` | Reviewed `dev → qa` PR triggers QA deployment and smoke verification |
| `stage` | `CC_PROJECT_STAGE` | Reviewed `qa → stage` PR triggers STAGE deployment and smoke verification |
| `main` | `CC_PROJECT_PROD` | Reviewed `stage → main` PR triggers PROD deployment, verification and AWS Lambda auditing |

The workflow copies reviewed DEV DDL **between Git branches**. It does not extract SQL back from QA, STAGE or PROD. PR checks enforce valid promotion order; branch rules require a passing `SQL Policy Check` and PR merge before promotion. The AWS audit role currently trusts `main` only, so CloudWatch deployment auditing runs for PROD only.

## Workflows and scripts

- `.github/workflows/sync-dev.yml` — manual DEV snapshot sync (run on `dev`)
- `.github/workflows/validate-sql.yml` — PR policy checks and offline unit tests (`SQL Policy Check`)
- `.github/workflows/deploy-environments.yml` — environment-specific deployment and verification (`qa`, `stage`, `main`), followed by AWS auditing for PROD
- `scripts/sync_dev.py` — discover objects in DEV and record `GET_DDL` snapshots
- `scripts/promote_snapshots.py` — validate snapshots and deploy only changed supported objects
- `scripts/verify_deployment.py` — verify target object metadata and compile views without reading rows
- `scripts/check_promotion_path.py` — block out-of-order snapshot PRs

## How to demonstrate

1. Create a new self-contained view in `CC_PROJECT_DEV.APP`.
2. Run **Sync Snowflake DEV snapshots** on the `dev` branch; review and merge the generated PR into `dev`.
3. Open and validate `dev → qa`; merge, then verify `CC_PROJECT_QA`.
4. Open and validate `qa → stage`; merge, then verify `CC_PROJECT_STAGE`.
5. Open and validate `stage → main`; review carefully, merge, verify `CC_PROJECT_PROD` and inspect the AWS Lambda/CloudWatch audit event.
6. As a negative test, open an invalid snapshot PR that skips an environment and confirm `SQL Policy Check` fails; do **not** merge it.

Run offline checks locally: `python3 -m unittest discover -s tests -v`.

## Scope and caveats

This is a controlled proof of concept, not a production migration engine. The SQL checks are intentionally limited: existing-table changes, deletions and unsupported definitions are not promoted automatically. The smoke checks do not validate data parity or execute procedures. Deployment failures may leave partial changes; there is no automatic rollback or cross-object dependency resolution. Branches are release records, not a full reconciliation of historic database objects. Only PROD invokes AWS Lambda today. See `docs/MULTI-ENV-PROMOTION.md` and `docs/DEPLOYMENT-VERIFICATION.md`.
