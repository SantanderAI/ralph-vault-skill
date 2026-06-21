# ralph-vault

> **Open source by Santander AI Lab.** A Python **CLI tool / library** to create and maintain a
> progressive-disclosure knowledge vault (a tiered "deepwiki") for one or many code repositories —
> the knowledge source for **LLM / AI agent** loops (ralph-style).

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/SantanderAI/ralph-vault-skill/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SantanderAI/ralph-vault-skill/actions/workflows/ci.yml)
[![CodeQL](https://github.com/SantanderAI/ralph-vault-skill/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/SantanderAI/ralph-vault-skill/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/SantanderAI/ralph-vault-skill/badge)](https://scorecard.dev/viewer/?uri=github.com/SantanderAI/ralph-vault-skill)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![GitHub last commit](https://img.shields.io/github/last-commit/SantanderAI/ralph-vault-skill)](https://github.com/SantanderAI/ralph-vault-skill/commits/main)
Part of [**Santander AI Open Source**](https://github.com/SantanderAI) — open source AI projects from Banco Santander ([santander.com](https://santander.com)).


---

A skill + CLI to **create and maintain a progressive-disclosure knowledge vault** (a tiered "deepwiki") for one or many code repositories, designed to be the knowledge source for [ralph](https://github.com/ghuntley/ralph)-style agent loops. Project-agnostic: documented repos live in a per-vault config registry, nothing is hardcoded.

## What it does

- **init** the tiered vault structure (`index`, `repos`, `components`, `infrastructure`, `technologies`, `relations`, … `meta`) + config.
- **add** / **delete** a repo or subdirectory to document.
- **update** repos that are new, incomplete, or stale (LLM work via FIXED prompts).
- **relations** / **dependencies** / **components** — graph tiers: typed edges between repos, external infra + providers (reverse index), and shared libraries reused by ≥ 2 repos.
- **validate** frontmatter / wikilinks / token budgets, plus a deterministic **no-source-code** gate and a **source-backlink** check.
- **check** what is missing / incomplete / stale.
- **plan** a ralph-loop (`plan/plan.md` + tasks) to (re)build the vault.

The split: `scripts/gv.py` owns everything deterministic; `assets/prompts/` are the immutable prompts that an agent/loop follows to write the content.

## Layout

```
ralph-vault/
├── SKILL.md              # entry point + action router (progressive disclosure)
├── agents/openai.yaml    # UI metadata
├── scripts/gv.py         # the CLI (stdlib only)
├── references/           # one doc per action, loaded on demand
└── assets/
    ├── prompts/          # FIXED prompts: bootstrap / sync / cross-link / relations / dependencies / components / judge
    ├── stack-tasks/      # per-stack section maps (python/java/node/go/frontend/scala/generic)
    └── templates/        # repo-section / repo-card / relation-edge / infrastructure-piece / technology / component / frontmatter-spec / config.example.json
```

## Usage

The way to use this is **as a skill**. Install it (see below), then just talk to
your agent (Claude / Codex / Gemini) in natural language — *"document this repo
into the vault"*, *"check what's stale"* — or invoke it explicitly with a slash
command. The agent reads `SKILL.md`, follows its action router, and drives
`scripts/gv.py` and the FIXED prompts in `assets/prompts/` for you. You don't run
the CLI by hand in the normal flow (that's the advanced path at the end of this
doc).

### Skill actions

The skill exposes these actions (its action router in `SKILL.md` maps each intent
to a reference under `references/`):

| Action | What it does |
|---|---|
| **init** | Create the tiered vault structure + `.ralphvault/config.json` if missing. Idempotent. |
| **add** | Register a repo or subdirectory in the config so it gets documented. Does not generate docs. |
| **delete** | Unregister a repo/subdir; with `--purge` also removes its docs on disk. |
| **update** | Document new repos and refresh incomplete/stale ones (LLM work via FIXED prompts, normally delegated to a ralph loop). |
| **plan** | Emit `plan/plan.md` + per-repo task files so a ralph loop can (re)build the vault one repo at a time. |
| **check** | Report what is missing / incomplete / stale (path-aware staleness). |
| **validate** | Frontmatter / wikilink / token-budget gate, plus the no-source-code and source-backlink checks. |
| **relations** | Generate typed edges between repos (graph tier). |
| **dependencies** | Catalogue external infra + providers as a reverse index. |
| **components** | Promote shared libraries/components reused by ≥ 2 repos. |
| **ci** | Wire git/CI gates so the vault can't silently drift. |

### How to invoke it

Same scenarios, two equivalent ways — an explicit slash command with parameters,
or plain natural language the agent maps to the skill:

| Scenario | Slash command | Natural language |
|---|---|---|
| Initialize a new vault | `/ralph-vault init --project myproj` | *"initialize a ralph vault for this project called myproj"* |
| Document this single repo | `/ralph-vault add --name my-svc --path . --stack auto` then `/ralph-vault plan --repo my-svc` | *"create a vault from this repo and document it"* |
| Add a remote repo | `/ralph-vault add --name billing --url https://git.example/billing.git --stack java` | *"add the billing repo at https://git.example/billing.git (java) to the vault"* |
| Add a module / subdirectory as its own unit | `/ralph-vault add --name shared-ui --path ../monorepo/packages/ui --stack frontend --subdir` | *"document the packages/ui subdirectory of the monorepo as its own unit"* |
| See what needs work | `/ralph-vault check` | *"check what's missing or stale in the vault"* |
| Plan a (re)build of everything that needs work | `/ralph-vault plan --needs-work` | *"plan a ralph loop to build everything that needs work"* |
| Update / refresh stale repos | `/ralph-vault plan --stale` → run the loop → `/ralph-vault validate` | *"update the vault, only the repos whose source changed"* |
| Add several new repos, then rebuild | `/ralph-vault add --name a --path ../a` · `/ralph-vault add --name b --path ../b` · `/ralph-vault plan --needs-work` | *"add repos a and b, then plan the loop to document them"* |
| Remove a repo and its docs | `/ralph-vault delete --name my-svc --purge` | *"remove my-svc from the vault and delete its docs"* |
| Validate before committing | `/ralph-vault validate` | *"validate the vault"* |

The core objective is to produce a **`plan/plan.md`** (plus per-repo task files):
a plain-Markdown, fresh-context plan that a **ralph loop** then refines and
executes one repo at a time. After `plan`, the agent's turn is normally done — it
hands you a `ralph-loop.sh <N> plan/plan.md` command and stops, and the loop does
the actual content generation following the FIXED prompts.

That said, the ralph loop is not mandatory: since the plan is just Markdown, you
can also ask **your own agent** (Claude / Antigravity / Devin / Codex) to execute
`plan/plan.md` directly — *"now follow plan/plan.md and document the repos"* — and
it will work through the tasks itself. The loop is the recommended path for large
vaults (it keeps each iteration in fresh context); driving it with your agent is
fine for one or a few repos.

## Install as a skill

Run the installer — it detects which agent tools are present and copies the skill
(as a `ralph-vault/` folder) into each skills directory it finds:

```bash
./install.sh            # install into every detected skills dir
./install.sh --dry-run  # preview only
./install.sh --force    # overwrite an existing install
./install.sh --dest ~/.codex/skills   # force a specific target
```

Detected targets: `${CODEX_HOME:-~/.codex}/skills`, `~/.claude/skills`,
`~/.gemini/antigravity-cli/skills`.

### Install / update via curl (no clone)

The same script runs piped from `curl`; it downloads a tarball of the repo and
installs it. Set `RALPHVAULT_REPO` (and optionally `RALPHVAULT_REF`, default
`main`) until a default host is baked in. Re-run anytime to update:

```bash
RALPHVAULT_REPO=owner/repo \
  curl -fsSL https://raw.githubusercontent.com/owner/repo/main/install.sh | bash

# update to a tag/branch, overwriting the existing install:
RALPHVAULT_REPO=owner/repo RALPHVAULT_REF=v1.2.0 \
  curl -fsSL https://raw.githubusercontent.com/owner/repo/v1.2.0/install.sh | bash -s -- --force
```

Or do it by hand:

```bash
cp -R ralph-vault "${CODEX_HOME:-$HOME/.codex}/skills/"
# or ~/.claude/skills/ , ~/.gemini/antigravity-cli/skills/ , etc.
```

The CLI has no dependencies beyond Python 3 and (optionally) `git` for staleness checks.

## Advanced: the `gv.py` CLI directly

In the normal flow you drive the skill (above), not the CLI. But `scripts/gv.py`
is a self-contained, dependency-free CLI you *can* run by hand — it's the same
backbone the skill calls — which is useful for scripting or debugging:

```bash
gv=scripts/gv.py
python3 $gv --vault vault init --project myproj
python3 $gv --vault vault add --name my-svc --path ../my-svc --stack auto
python3 $gv --vault vault plan --needs-work   # → plan/plan.md + plan/task/NN.md (only affected entries)
ralph-loop.sh 30 plan/plan.md                 # drive generation (any ralph runner)
python3 $gv --vault vault validate            # gate
python3 $gv --vault vault check               # status (path-aware staleness)
python3 $gv --vault vault mark-synced --repo my-svc   # close: advance last_sync_commit + log to meta/changelog.md
python3 $gv --vault vault mark-reconciled --repo my-svc  # close an omission audit: advance last_reconcile_commit
python3 $gv --vault vault changelog --repo my-svc     # read the sync log (filters: --repo, --since, --limit)
```

The content-generation steps still need an agent/ralph loop following the FIXED
prompts in `assets/prompts/` — the CLI only does the deterministic parts.

## Requirements

- **Python >= 3.10** (standard library only — no third-party runtime dependencies)
- **git** *(optional)* — used for path-aware staleness checks

## Contributing

We welcome contributions from the community. Please read our
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.
By contributing, you agree to the terms of our Contributor License Agreement (CLA),
which the CLA Assistant bot will prompt you to sign on your first PR.

## Security

To report a security vulnerability, please follow the process described in
[SECURITY.md](.github/SECURITY.md). **Do not open a public issue for security vulnerabilities.**

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE)
file for details.

```
Copyright (c) 2026 Santander Group
SPDX-License-Identifier: Apache-2.0
```

## Citation

If you use this tool in your work, please cite:

```bibtex
@software{ralph_vault_skill,
  title  = {ralph-vault: a progressive-disclosure knowledge vault skill},
  author = {Santander AI Lab},
  year   = {2026},
  url    = {https://github.com/SantanderAI/ralph-vault-skill},
  license = {Apache-2.0}
}
```

🍻
