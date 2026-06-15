# FIXED prompt — sync (incremental refresh of one repo)

> Immutable per release. One Ralph iteration = one task. Use when a repo is already `phase: done` and its source moved on.

## Role

Same as `bootstrap.md`, in `sync` mode: refresh only the documentation whose source surface actually changed since `last_sync_commit`.

## Inputs

`bootstrap.md` inputs plus:

- `LAST_SYNC_COMMIT` — recorded short SHA.
- `HEAD_COMMIT` — current short SHA of the source.

## Algorithm (one branch, then stop)

1. **Diff scope**: the **task file already lists the affected docs**, computed deterministically by `gv.py plan` from each doc's `source_globs` vs the `LAST_SYNC_COMMIT..HEAD` diff. Use that list. Only if the task says no `source_globs` are declared yet (legacy docs), fall back to mapping changed paths to sections by keyword:
   - api/controllers/routes → `apis`
   - domain/model/entities → `domain-model`
   - repository/migrations/schema → `data-model`
   - config/env/ci/docker/k8s → `configuration`
   - dependency manifests → `integrations`
   - tests → `quality`
   - new/removed modules → `architecture` (+ module docs)
   In the fallback case, also **add `source_globs`** to each regenerated doc so future syncs scope to modules.
2. **Regenerate one affected doc** fully (do not patch in place). Update frontmatter: `commit: HEAD_COMMIT`, `last_sync: now`. **Preserve** all other existing frontmatter fields, including `source_globs`. If content is unchanged modulo timestamps, still bump only the timestamps and trace `NOOP`. Stop.
3. **Self-validate + close** (when queue empty): run `gv.py validate`; fix this repo's errors if any (stop), else **close with `gv.py mark-synced --repo {NAME}`** — it advances `last_sync_commit` and logs the commit→docs mapping to `meta/changelog.md`. Do not hand-edit `config.json`. Stop.

## Hard rules

All `bootstrap.md` hard rules apply. Additionally:

- **Aggressive progressive disclosure**: read only the changed paths in the diff + the single affected section being regenerated. Never re-read the whole repo.
- **Never regenerate sections outside the affected set** listed in the task — protect untouched docs from drift.
- **Never strip frontmatter fields** that already exist (especially `source_globs`); sync only updates `commit` / `last_sync`.
- **Close via `gv.py mark-synced`**, never by hand-editing `config.json`.

## Output trace

```
DIFF · {NAME} · {K} sections affected
ITER OK · {NAME} · {section} · remaining: {N}
ITER NOOP · {NAME} · {section} · no surface change
DONE · {NAME}
```
