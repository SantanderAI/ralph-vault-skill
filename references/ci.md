# Action: ci (drift gates)

Wire the vault into git so it cannot silently drift from the code. Two templates ship
under `assets/templates/`; both are thin wrappers around the deterministic CLI
(`gv.py validate` + `gv.py check --gate`) — no new logic, no dependencies.

## Templates

- **`assets/templates/pre-commit.sh`** — a git hook. Runs `validate` as a hard gate
  (structure must always be valid) and `check` as an advisory print (drift is expected
  mid-work, so it does **not** block by default). Export `RALPHVAULT_STRICT=1` to also
  gate on drift locally.
- **`assets/templates/vault-check.yml`** — a GitHub Actions workflow. Runs `validate`
  **and** `check --gate`, so a PR/push fails when a repo is missing docs, still pending,
  or stale. This is where drift should hard-fail.

## Install

```bash
# pre-commit hook (in the repo that owns the vault)
cp <skill>/assets/templates/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# CI gate
cp <skill>/assets/templates/vault-check.yml .github/workflows/vault-check.yml
```

Both read `RALPHVAULT_VAULT` (default `vault`) and `RALPHVAULT_GV` (default
`scripts/gv.py`); set them if your layout differs.

## Why pre-commit is soft but CI is hard

Blocking every commit on a stale/pending repo makes mid-task work painful. So the hook
only enforces structure, and CI enforces freshness at the merge boundary — where you can
require the docs to be re-planned and synced before the change lands.

## Caveat — source checkout

Staleness is computed from the git history of each entry's `source` path. The CI gate is
only meaningful when those sources are checked out in the job (vault in the same
repo/monorepo as the code; `fetch-depth: 0` so history is present). For `url` or
out-of-repo sources, CI enforces `validate` and docs-existence but cannot detect drift —
run `update` on a schedule for those.
