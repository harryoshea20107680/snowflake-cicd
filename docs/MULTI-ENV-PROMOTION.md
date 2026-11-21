# Multi-environment Snowflake CI/CD proof of concept

## Target branch and database mapping

| Git branch | Snowflake database | How it changes |
|---|---|---|
| `dev` | `CC_PROJECT_DEV` | Developer edits in Snowflake DEV, then manually runs `sync-dev.yml` on `dev`, opens PR from generated snapshot branch into `dev` |
| `qa` | `CC_PROJECT_QA` | PR **dev → qa**, validate, merge; deploy and verify on qa push |
| `stage` | `CC_PROJECT_STAGE` | PR **qa → stage**, validate, merge; deploy and verify on stage push |
| `main` | `CC_PROJECT_PROD` | PR **stage → main**, validate, approve, merge; deploy and verify on main push, then invoke AWS Lambda audit |

Snapshot files are captured **only from DEV**. Subsequent PRs promote the same approved SQL text; they must not re-extract QA/STAGE and overwrite version-controlled source definitions. `dev` has no deployment workflow because changes are already made there in Snowflake.

## Critical setup order

1. Open the infrastructure PR **against existing `main`**. It changes the original deploy-qa workflow into a multi-environment workflow, so no duplicate main→QA deployments can occur.
2. Merge the infrastructure PR after checks pass.
3. **Only after the merge**, create `dev`, `qa` and `stage` from the updated main commit. This ensures each long-lived branch has the required workflow files and scripts.
4. In GitHub Settings > Branches/Rulesets, protect **all four branches** from direct snapshot pushes and force pushes, require `SQL Policy Check` on PRs, and require a reviewer approval for `main` production promotion. The source-route validation will reject out-of-order snapshot PRs; branch protection stops people skipping PRs entirely.
5. Ensure the Snowflake GitHub OIDC service user can authenticate from qa/stage/main branches, and that `GITHUB_CICD_ROLE` has the required (carefully scoped) privileges on the QA/STAGE/PROD target databases, schemas, and warehouse. Branch-specific Snowflake deploy roles would be preferable beyond this POC.
6. Confirm AWS IAM role trust still covers `main`. To preserve the currently working AWS IAM trust, this first iteration sends **PROD/main deployment audits only**. QA/STAGE remain visible in GitHub Actions. Extend AWS trust deliberately before enabling their AWS audit jobs.
7. Make a **new self-contained view** in DEV (e.g. `SELECT 1`) and promote it dev → qa → stage → main. Avoid expecting existing historical main snapshots to have been deployed to STAGE/PROD: baseline differences require reconciliation.

## First end-to-end demo

- On `dev` run the **Sync Snowflake DEV snapshots** workflow, then open the generated PR to `dev`.
- Open dev→qa PR, merge, and observe `CC_PROJECT_QA` deployment and independent verification.
- Open qa→stage PR, merge, and observe `CC_PROJECT_STAGE` deployment and independent verification.
- Open stage→main PR, review and approve, merge, and observe `CC_PROJECT_PROD` deployment, independent verification, and CloudWatch PROD audit event.
- Try a PR directly from dev→stage (with snapshot changes) and confirm the route check rejects it; do not merge.

## Constraints and limitations

- Git branches are **versioned release records**, not direct proof that every SQL object already exists in its mapped database. Existing `main` snapshots were previously QA snapshots; backfill or reconcile before claiming complete STAGE/PROD parity.
- Validation is a conservative, intentionally limited single-DDL policy, not a general SQL parser. Existing table modifications, dropped snapshots, and unsafe/unknown definitions fail closed on promotions.
- `--source-sync` relaxes table-change rejection only for DEV snapshot review; changes still cannot promote to QA without a migration process.
- New tables are created only if absent in the target, which may require reconciliation for pre-existing manually created tables.
- Procedures are not executed by smoke checks. Cross-object dependencies, data migration, grants on replaced objects, reversions, drift detection, and automatic rollback are not yet supported.
- Workflow push triggers depend on GitHub branch rules. Without branch protection, users with write access could push directly to an environment branch and bypass PR route checks.
- `SNOWFLAKE_TARGET` controls the destination (QA/STAGE/PROD); no target outside those three is accepted.
- Audit job logs deployment **outcomes**, not guaranteed database transactional state. Failed deployments may have partially applied changes.
