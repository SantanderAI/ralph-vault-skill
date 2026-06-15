# Action: check

Status overview of the registry: what is missing, incomplete, or stale. Read-only.

## Do

```bash
python3 scripts/gv.py --vault vault check          # report only
python3 scripts/gv.py --vault vault check --gate   # exit 1 if anything needs attention
```

## Flags per repo

- **MISSING-DOCS** — no `.md` under `repos/<name>/`.
- **MISSING-CARD** — no `agent-context/repo-cards/<name>.md`.
- **phase=pending** — never bootstrapped to `done`.
- **STALE(...)** — the last commit that touched the `source` path differs from the recorded `last_sync_commit` (only for `source_kind: path`). Path-aware, so a `subdir` entry is flagged only when its own subtree changed, not on every monorepo commit.

A repo with none of these prints `[ok] <name>: up to date`.

## Advisories (non-gating, `[~]`)

- **stack with no tailored section map** — falls back to `generic`.
- **stale repo referenced by N graph doc(s)** — when a repo is stale, the `relations`/`components`/`infrastructure`/`technologies` docs that wikilink to it may be outdated; re-plan to refresh the graph.
- **no `source_globs`** (reported by `validate`) — that repo's sync falls back to a whole-repo refresh instead of module-level.

## Typical use

- Before a release / in CI with `--gate` to fail when the vault drifts from the code. Ready-made git hook + GitHub Actions templates live in `assets/templates/` — see `references/ci.md`.
- To decide the scope of the next **update**: `gv.py plan --needs-work` plans exactly the flagged entries (pending, missing docs/card, or stale); `gv.py plan --stale` plans only already-done entries whose source moved.

## Note

Remote (`url`) sources cannot be staleness-checked without cloning; `check` only verifies their docs exist. Use **update** on a schedule for those.
