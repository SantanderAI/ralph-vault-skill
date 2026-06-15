---
name: ralph-vault
description: >-
  Create and maintain a project-agnostic deepwiki knowledge vault — a tiered,
  progressive-disclosure documentation base for one or many code
  repos/subdirectories, designed as the knowledge source for ralph-loop agents.
  Use when the user wants to initialize a vault, document or refresh repos, add
  or remove a repo or subdirectory from the vault, validate the vault, check what
  is missing or stale, or generate a ralph-loop plan to (re)build it. Triggers
  include create/init a vault, document this repo, update the vault, add a repo
  to the vault, validate the vault, vault status, knowledge base for ralph.
---

# Ralph Vault

Lifecycle tool for a **knowledge vault**: a tiered deepwiki that documents the intent, interfaces and structure of one or more code repositories, kept faithful and current so agents (especially ralph loops) have a reliable knowledge source. Project-agnostic — the documented repos live in a per-vault config registry, nothing is hardcoded.

## How it is split

- **Deterministic work → `scripts/gv.py`** (a single stdlib CLI): scaffolding, the repo registry, status, validation, and emitting ralph plan files. Run it directly; it needs no context loaded.
- **Content generation → FIXED prompts in `assets/prompts/`** driven by an agent / ralph loop: writing the actual documentation from source.

Run `gv.py` from the project that owns the vault. Default vault path is `vault/`; override with `--vault <path>`.

## Action router

Load the matching reference file **only** for the action at hand (progressive disclosure). Do not preload all of them.

| Intent | Action | Load |
|---|---|---|
| Create the vault structure + config if missing | **init** | `references/init.md` |
| Register a repo or subdirectory to document | **add** | `references/add.md` |
| Remove a repo/subdir (optionally purge docs) | **delete** | `references/delete.md` |
| Document or refresh repos (incomplete/stale) | **update** | `references/update.md` |
| Generate typed edges between repos | **relations** | `references/relations.md` |
| Catalogue external infra + providers (reverse index) | **dependencies** | `references/dependencies.md` |
| Promote components/libraries reused by ≥ 2 repos | **components** | `references/components.md` |
| Frontmatter / wikilink / budget gate | **validate** | `references/validate.md` |
| Report what is missing / incomplete / stale | **check** | `references/check.md` |
| Emit `plan/plan.md` + tasks for a ralph loop | **plan** | `references/plan.md` |
| Wire git/CI gates so the vault can't drift | **ci** | `references/ci.md` |

Shared contracts (load when authoring or validating content, not for routine CLI calls):

- `references/vault-structure.md` — the tier layout, load tiers, and frontmatter contract.
- `references/config.md` — the `.ralphvault/config.json` registry schema.

## Quick start

```bash
gv=scripts/gv.py                      # path to this skill's CLI
python3 $gv --vault vault init --project myproj
python3 $gv --vault vault add --name my-svc --path ../my-svc --stack auto
python3 $gv --vault vault plan --needs-work        # → plan/plan.md + plan/task/NN.md (only affected entries)
ralph-loop.sh 30 plan/plan.md                     # drive generation (any ralph runner)
python3 $gv --vault vault validate                # gate before committing
python3 $gv --vault vault check                   # status overview (path-aware staleness)
```

## Hard rules

- **Phase separation (agent vs loop)**: the agent only runs the deterministic CLI actions (`init`, `add`, `delete`, `plan`, `validate`, `check`, `mark-synced`) and never authors vault content itself. All content generation (`update`/bootstrap/sync, `relations`, `dependencies`, `components`) is delegated to a ralph loop. After `plan`, the agent's turn is **done**: return the `ralph-loop.sh <N> plan/plan.md` command and stop — do not open subagents or write into `repos/`, `relations/`, `infrastructure/`, `technologies/`, `components/` yourself. Generate content directly **only** if the user explicitly asks for it.
- **Never copy source code** into the vault. Extract intent, interfaces, structure, named entities only.
- **Aggressive progressive disclosure**: load the minimum context for the current single task. Start from tier-1 cards (`agent-context/repo-cards/*`); descend into deeper tiers or read source only when the task cannot be completed otherwise. Never preload whole repos, all docs, or unrelated tiers.
- **Always** stamp frontmatter + provenance (`commit`, `last_sync`) on repo-derived docs — see `references/vault-structure.md`.
- **Validate before done**: any generation task (run by the loop, or by the agent only when the user explicitly asked) is not finished until `gv.py validate` reports zero errors for the touched files. For the agent, a `plan` handoff is "done" once the plan files are emitted and the command is returned.
- **One repo per ralph iteration**: keep generation tasks atomic so a fresh-context loop stays deterministic.
- **Incremental & path-aware**: staleness and sync scope are computed from the last commit touching each entry's `source` (so a `subdir` is not flagged on unrelated monorepo commits), and from each doc's `source_globs` (so a sync regenerates only the changed modules). Close every generation via `gv.py mark-synced` (advances `last_sync_commit` + logs commit→docs to `meta/changelog.md`); never hand-edit `config.json`.
- **Nothing project-specific lives in the skill**: repos, URLs, stacks and budgets come from the vault's config, never from edits to these files.
