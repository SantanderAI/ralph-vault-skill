# Action: plan

Emit ralph-loop plan files so a fresh-context loop can generate/refresh the vault one repo at a time.

## Do

```bash
python3 scripts/gv.py --vault vault plan              # all registered repos
python3 scripts/gv.py --vault vault plan --needs-work # pending OR missing docs/card OR stale (recommended)
python3 scripts/gv.py --vault vault plan --stale      # only done repos whose source path moved
python3 scripts/gv.py --vault vault plan --pending    # only phase != done
python3 scripts/gv.py --vault vault plan --repo my-svc
python3 scripts/gv.py --vault vault plan --plan-dir plan   # output dir (default: plan)
```

**Only affected entries are planned**: `--needs-work`/`--stale` use the same path-aware staleness as `check`, so a `subdir` is planned only when its own subtree changed.

## Output

- `plan/plan.md` — canonical **loop instructions** (one subtask per iteration, `stop.md` to halt) + a checkbox task list, one line per repo, each linking a task file. Picks `bootstrap` for `phase: pending`, `sync` for `done`.
- `plan/task/NN.md` — per-repo task: source/stack/kind, the FIXED prompt to follow, and atomic subtasks ending in a `gv.py validate` gate, a `[juez]` checkpoint, and a `gv.py mark-synced` close.
  - For **sync** tasks the file carries a **Diff scope** block: the `last_sync_commit..HEAD` changed files and the exact docs to regenerate, resolved from each doc's `source_globs`. The loop regenerates only those (module-level incremental refresh).
- **Graph tasks (appended after the repo tasks)** — every plan also emits `relations`, `components` and `dependencies` tasks (driven by `assets/prompts/relations.md` / `components.md` / `dependencies.md`), so rebuilding/refreshing repos also refreshes the cross-repo graph and the external-dependency index. They run last (after the repo docs they depend on exist). Skip all with `--no-graph`. Per-tier threshold: `relations` and `components` need ≥ 2 registered repos; `dependencies` is emitted from a single repo (it consumes external infra/providers regardless).

## Drive it

Any ralph runner works since the plan is plain Markdown:

```bash
ralph-loop.sh 30 plan/plan.md
```

Each iteration documents one section/repo, validates, and stops — continuity lives in the vault + the checkboxes, not in context.

## Notes

- **Emitting the plan is the end of the agent's turn** — hand the `ralph-loop.sh <N> plan/plan.md` command to the user and stop; do not chain into generation yourself (see the **Phase separation** hard rule in `SKILL.md`).
- The `[juez]` checkpoint integrates with ralph's `juez` skill if present; otherwise it is a manual review step.
- Re-running `plan` regenerates the files; safe to overwrite.
