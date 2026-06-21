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
- **change-drift → regenerate N section(s)** — a stale repo's changed files mapped (via `source_globs`) to the exact docs that own them, so the loop knows *what* to regenerate, not merely *that* something moved.
- **N source file(s) not covered by any section's `source_globs` — possible omission** — tracked source files that no doc claims. Deterministic, language-agnostic, file-level: catches files undocumented since the original sync — the blind spot commit-equality reports as "up to date" forever. It cannot see uncovered items *inside* a covered file (e.g. a new route in an already-documented controller); that is the LLM reconcile pass's job. Only computed once a repo declares `source_globs`.
- **reconcile due (N commits since last audit)** — a `done` repo whose source has moved more than `reconcile_after_commits` (default 25) since its last full omission audit, or that was never audited. Plan it with `gv.py plan --reconcile` (or `--needs-work`) to drive a `reconcile` task that re-reads the surface and documents anything missing *inside* covered files. This is the LLM counterpart to the deterministic file-level coverage check.
- **stale repo referenced by N graph doc(s)** — when a repo is stale, the `relations`/`components`/`infrastructure`/`technologies` docs that wikilink to it may be outdated; re-plan to refresh the graph.
- **no `source_globs`** (reported by `validate`) — that repo's sync falls back to a whole-repo refresh instead of module-level.

## Typical use

- Before a release / in CI with `--gate` to fail when the vault drifts from the code. Ready-made git hook + GitHub Actions templates live in `assets/templates/` — see `references/ci.md`.
- To decide the scope of the next **update**: `gv.py plan --needs-work` plans exactly the flagged entries (pending, missing docs/card, or stale); `gv.py plan --stale` plans only already-done entries whose source moved.

## Note

Remote (`url`) sources cannot be staleness-checked without cloning; `check` only verifies their docs exist. Use **update** on a schedule for those.
