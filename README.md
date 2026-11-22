# Snowflake CI/CD — Cloud Computing Project

A university proof of concept for promoting Snowflake database objects through **DEV → QA → STAGE → PROD** using GitHub Actions, Snowflake OIDC and AWS Lambda/CloudWatch.

## Architecture

| Git branch | Snowflake database |
|---|---|
| `dev` | `CC_PROJECT_DEV` |
| `qa` | `CC_PROJECT_QA` |
| `stage` | `CC_PROJECT_STAGE` |
| `main` | `CC_PROJECT_PROD` |

SQL definitions are stored in `database/APP/` on each branch. Snowflake DEV is the source of the definitions; approved pull requests promote those files in order from `dev` to `main`.

## Implemented

- **DEV sync:** `GET_DDL` captures tables, views and procedures from Snowflake DEV into Git.
- **PR validation:** the `SQL Policy Check` runs Python tests and checks SQL safety and promotion order.
- **Deployment:** GitHub Actions deploys changed SQL to QA, STAGE and PROD using Snowflake OIDC authentication.
- **Verification:** post-deployment checks confirm object metadata and view compilation.
- **Audit:** AWS OIDC invokes a Lambda function after QA, STAGE and PROD deployment attempts; the function records audit information in CloudWatch.

## End-to-end demonstration

`CICD_CANONICAL_DATABASE_V` was captured from DEV and promoted successfully through all four environments:

| Step | Evidence |
|---|---|
| DEV capture | [PR #46](https://github.com/harryoshea20107680/snowflake-cicd/pull/46) |
| QA deployment and audit | [Run #45038206116](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45038206116) |
| STAGE deployment and audit | [Run #45038636180](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45038636180) |
| PROD deployment and audit | [Run #45039057826](https://github.com/harryoshea20107680/snowflake-cicd/actions/runs/45039057826) |

## Repository contents

- `database/APP/` — version-controlled SQL definitions
- `.github/workflows/` — DEV sync, PR validation, deployment and OIDC connection check
- `scripts/` — Python sync, policy, deployment and verification logic
- `tests/` — automated tests run by the PR validation workflow
- `docs/` — brief [architecture](docs/MULTI-ENV-PROMOTION.md) and [verification](docs/DEPLOYMENT-VERIFICATION.md) notes

**Scope:** This is an academic proof of concept, not a production migration framework. It does not provide automatic rollback, full data-parity checks or automatic migration of existing tables.
