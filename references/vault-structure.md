# Vault structure & frontmatter contract

The vault is organized in **tiers** for progressive disclosure: load Tier 0/1 first, descend only when a task needs it. `gv.py init` scaffolds every tier with a `README.md` index.

| Tier | Purpose | load_tier |
|---|---|---|
| `index` | Cross-repo indexes: repo list, tech-stack map, domain map. | 1 |
| `domains` | Bounded contexts identified across repos. | 2 |
| `repos` | Per-repo deep docs (one folder per registered repo). | 2 |
| `components` | Shared components/libraries reused across ≥ 2 repos. | 2 |
| `infrastructure` | Deployable infra pieces the system runs on. | 2 |
| `technologies` | External SDKs/providers consumed by repos. | 2 |
| `relations` | Typed edges between repos (`grpc/http/kafka/db/code/secret/apm`). | 2 |
| `cross-cutting` | Shared concerns: auth, errors, observability, testing. | 2 |
| `adrs` | Architecture decision records. | 3 |
| `glossary` | Canonical terms (`terms.md`). | 2 |
| `agent-context` | Tier-1 repo cards, codegen rules, loading recipes. | 1 |
| `meta` | Vault hygiene: pending queues, this spec, `changelog.md`. | never |

Two non-tier folders also exist at the vault root: `assets/` (images/diagrams referenced from docs, not loaded as context) and `LAST-UPDATED.md` (vault-wide timestamp, rewritten by `gv.py` on every mutation). The per-sync audit log (which commits touched which docs, and when) lives separately in `meta/changelog.md`, appended by `gv.py mark-synced` — do not conflate it with the `LAST-UPDATED.md` timestamp.

## Per-repo layout (`repos/<name>/`)

Generate the sections relevant to the repo's stack (see `assets/stack-tasks/<stack>.md`). Common set:

```
repos/<name>/
├── README.md         # section index (type: section-readme)
├── overview.md       # purpose, responsibilities, entry points
├── architecture.md   # modules, layering, key flows
├── domain-model.md   # entities, aggregates, invariants
├── apis.md           # public interfaces / endpoints
├── data-model.md     # persistence, schemas, migrations
├── integrations.md   # external deps, messaging, contracts
├── configuration.md  # config, env, deployment
└── quality.md        # tests, CI, observability
```

Plus a tier-1 card at `agent-context/repo-cards/<name>.md` (≤ ~1000 tokens, `load_tier: 1`).

## Graph tiers layout

```
relations/<kind>/<from>_<kind>_<to>.md   # one typed edge; kind ∈ grpc|http|kafka|db|code|secret|apm|other
infrastructure/<name>.md                 # one deployable piece + reverse "repos that use it"
technologies/<name>.md                   # one external SDK/provider + reverse "repos that use it"
components/<name>.md                      # one shared component reused by ≥ 2 repos
```

- **Relations** carry `from`, `to`, `relation_type` in frontmatter (validator errors if missing); both `from`/`to` must resolve to a registered repo. One direction per file. See `references/relations.md`.
- **Infrastructure / technologies** each list the consuming repos with evidence (reverse index). See `references/dependencies.md`.
- **Components** are promoted only when reused by ≥ 2 repos; single-repo pieces stay in `repos/<name>/modules/`. See `references/components.md`.

## Frontmatter contract

Every `.md` (except tier READMEs which `init` writes) needs YAML frontmatter. Required fields are configurable in `.ralphvault/config.json` (`settings.required_frontmatter`); default: `type`, `load_tier`, `schema_version`.

Repo-derived docs additionally stamp provenance:

```yaml
---
type: repo-doc            # or: repo-readme | module | repo-card | adr | section-readme
load_tier: 2
schema_version: 1
repo: <name>
source: <path-or-url>
commit: <short SHA at read time>
last_sync: <ISO 8601 UTC datetime>
stack: <detected stack>
source_globs: [<paths this doc covers, relative to source; supports * ? **>]
tags: [<name>, <section>]
---
```

`source_globs` is what lets `gv.py plan` scope a **sync** to only the docs whose source changed since `last_sync_commit` (module-level incremental refresh). Stamp it on every `repo-doc`/`module`; never strip it on sync.

## Evidence — backlink to source

Leaf docs (`repo-doc`, `module`) must keep a link back to the original code: know the architecture without loading modules, yet always be able to descend to the real source. End each with an `## Evidence` block citing the files it summarizes — use `path` or `path#Symbol`, **never line numbers** (they rot on every commit). The validator warns when such a doc cites no source path. Doc-level provenance (`source` + `commit`) is the coarse link; Evidence is the fine-grained one.

## Wikilinks

Use `[[path/to/doc#Heading|alias]]` with vault-root-relative paths. Verify the anchor matches a real heading before writing (the validator flags broken targets as errors, broken anchors as warnings). Never wrap wikilinks in backticks.
