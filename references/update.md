# Action: update

Document new repos and refresh incomplete/stale ones. This is **LLM work** driven by the FIXED prompts; the CLI prepares and gates it.

## Flow

```bash
# 1. see what needs work
python3 scripts/gv.py --vault vault check

# 2. emit a ralph plan for everything that needs work (pending + stale), or one repo
python3 scripts/gv.py --vault vault plan --needs-work    # or: --stale | --pending | --repo <name>

# 3. drive generation with any ralph runner (fresh context per iteration)
ralph-loop.sh 30 plan/plan.md

# 4. gate
python3 scripts/gv.py --vault vault validate
```

## Bootstrap vs sync

The plan picks the mode per repo from its `phase`:

- **bootstrap** (`phase: pending`) → full first-time generation using `assets/prompts/bootstrap.md` + `assets/stack-tasks/<stack>.md`.
- **sync** (`phase: done`) → diff-driven refresh using `assets/prompts/sync.md`; regenerate only the sections whose source surface changed since `last_sync_commit`.

## Default: delegate, don't generate

By default the agent does **not** write content. Run `gv.py plan` (step 2), return `ralph-loop.sh <N> plan/plan.md`, and stop — the loop does the generation. See the **Phase separation** hard rule in `SKILL.md`.

## Manual (no ralph) single-repo refresh — opt-in only

**Only when the user explicitly asks the agent to generate directly.** Otherwise delegate via the plan above. If asked: load `assets/prompts/bootstrap.md` (or `sync.md`), follow it against the repo's `source`, write into `repos/<name>/` + the repo-card (stamping `source_globs`), run `gv.py validate`, then close with `gv.py mark-synced --repo <name>` (never hand-edit `config.json`).

## Incremental refresh (only affected modules)

For already-documented repos, `plan` is **path-aware and module-scoped**: it diffs `last_sync_commit..HEAD` for the entry's `source` and, using each doc's `source_globs`, writes into the sync task **only the docs whose source changed**. Untouched docs are left alone. Stamp `source_globs` on every doc at bootstrap so this works.

## Definition of done (per repo)

- Per-section docs + `repos/<name>/README.md` + `agent-context/repo-cards/<name>.md` exist.
- `gv.py validate` reports zero errors for those files.
- Closed with `gv.py mark-synced --repo <name>`: sets `phase: done`, advances `last_sync_commit`, and logs the commit→docs mapping to `meta/changelog.md`. **Do not hand-edit `config.json`.**
