# FIXED prompt — reconcile (omission audit of one repo)

> Immutable per release. One Ralph iteration = one task. Use when `gv.py plan` emits a `reconcile` task: a repo is `phase: done` and an omission audit has fallen due by the commit cadence (`reconcile_after_commits`).

## Role

You are auditing **completeness**, not refreshing changed code. The repo's docs may have been faithful to *what changed* yet never covered something that already existed at bootstrap time — the blind spot that commit-equality reports as "up to date" forever, and that file-level coverage cannot see when the omission lives *inside* an already-covered file. Your job: enumerate the source's surface, find what the docs do not account for, and document only the gaps.

## Inputs

`bootstrap.md` inputs plus:

- `LAST_RECONCILE_COMMIT` — baseline of the previous audit (or `None`).
- `HEAD_COMMIT` — current short SHA of the source.

## Algorithm (one branch, then stop)

1. **Enumerate the surface**: list the public/enumerable items the stack exposes — routes, CLI subcommands, exported symbols, env vars, DB tables/migrations, message/event types, config flags, whatever applies. Read the source for this; do not infer from the docs.
2. **Match against the docs**: for each item, confirm it is accounted for under `repos/{NAME}/` — either literally (the id appears) or subsumed by an explicit summary. Build the list of **gaps** (items present in code, absent from docs).
3. **Document the gaps**: for each gap, extend the **owning section** (do not rewrite the section, do not touch sections with no gap). Keep/stamp `source_globs` so the next file-level coverage check sees the new coverage. If a gap belongs to no existing section, add a module doc.
4. **Self-validate + close**: run `gv.py validate`; fix this repo's errors if any (stop), else **close with `gv.py mark-reconciled --repo {NAME}`** — it advances `last_reconcile_commit` and logs the audit to `meta/changelog.md`. Do not hand-edit `config.json`. Stop.

## Hard rules

All `bootstrap.md` hard rules apply. Additionally:

- **Audit, don't rewrite**: only add what is missing. Untouched, faithful sections stay byte-for-byte.
- **Never copy source code**: document the existence and intent of an item at the vault's abstraction level — never paste its body.
- **No silent drop**: if an item is deliberately out of altitude, say so in the section (a one-line "not documented: X — reason") rather than leaving it invisible.
- **Close via `gv.py mark-reconciled`**, never by hand-editing `config.json`. An audit that finds zero gaps still closes (it advances the baseline).

## Output trace

```
AUDIT · {NAME} · {K} surface items · {G} gaps
GAP · {NAME} · {section} · {item}
ITER OK · {NAME} · {section} · remaining gaps: {N}
DONE · {NAME} · reconciled at {HEAD_COMMIT}
```
