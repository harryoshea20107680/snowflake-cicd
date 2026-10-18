# Snowflake DEV snapshots to approved QA promotion

This patch changes the QA pipeline to use reviewed GitHub snapshot files.

## Contents
- `scripts/promote_qa.py`: validate snapshot diffs, then deploy approved changes.
- `.github/workflows/validate-sql.yml`: keep the existing required `SQL Policy Check` and add snapshot-specific checks.
- `.github/workflows/deploy-qa.yml`: deploy changed snapshots automatically when merged into `main`.

## Behaviour
- New tables: `CREATE TABLE IF NOT EXISTS` after checking that the table does not already exist in QA.
- Modified tables: rejected (a migration is required).
- New/modified views or procedures: deploy from approved snapshot DDL, in the matching QA schema.
- Deleted/inaccessible snapshots: rejected, without automatic destructive deletion.
- Unchanged objects: not deployed again.

## Install
From the `snowflake-cicd` repo root:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/snapshot-qa-promotion
unzip -o ~/Downloads/snapshot-qa-promotion.zip -d .
git add scripts/promote_qa.py .github/workflows/validate-sql.yml .github/workflows/deploy-qa.yml
git commit -m 'Deploy approved DEV snapshots safely to QA'
git push -u origin feature/snapshot-qa-promotion
gh pr create --base main --head feature/snapshot-qa-promotion --title 'Deploy approved DEV snapshots to QA' --body 'Dynamic snapshot-driven promotion with fail-closed table migration safety checks.'
```

## End-to-end test
1. Merge the implementation PR when `SQL Policy Check` passes.
2. Create a NEW view directly in Snowflake DEV under the developer role, referencing objects without qualified DEV database names.
3. Run `Sync Snowflake DEV snapshots` on `main`.
4. Open a PR from the created sync branch; review its DDL and verify the required SQL check.
5. Merge the snapshot PR. A push to main under `dev-snapshots/**` triggers QA deployment automatically.
6. Confirm the new view exists and queries successfully in QA.

## Known limits
- Not a comprehensive SQL parser or security checker. Reviewed source changes are still essential.
- Existing-table structural modifications are rejected until migration support is built.
- DROP/rename events, other Snowflake object types, and table row data are not promoted.
- Cross-object dependencies, grants on replaced views, and schema migrations need more advanced handling.
- DEV synchronization remains manual-triggered; no real-time CDC mechanism is configured.
- A required passing status check does not itself guarantee independent human approval.
