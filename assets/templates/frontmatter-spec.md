# Frontmatter spec (by path)

`type` and `load_tier` are dictated by where the file lives. The validator enforces the fields in `settings.required_frontmatter` (default: `type`, `load_tier`, `schema_version`).

| Path pattern | type | load_tier |
|---|---|---|
| `<vault>/README.md` | `vault-readme` | 0 |
| `<tier>/README.md` | `section-readme` | per tier |
| `repos/<name>/README.md` | `section-readme` | 2 |
| `repos/<name>/<NN>-*.md` | `repo-doc` | 2 |
| `repos/<name>/modules/*.md` | `module` | 2 |
| `agent-context/repo-cards/*.md` | `repo-card` | 1 |
| `agent-context/*` (other) | `agent-context` | 1 |
| `adrs/*.md` | `adr` (+ `adr_number`, `status`) | 3 |
| `index/*`, `domains/*`, `cross-cutting/*` | `index` / `domain` / `cross-cutting` | 1 / 2 / 2 |
| `relations/<kind>/*.md` | `relation` (+ `from`, `to`, `relation_type`) | 2 |
| `infrastructure/*.md` | `infrastructure` | 2 |
| `technologies/*.md` | `technology` | 2 |
| `components/*.md` | `component` (+ `owner_repo`) | 2 |
| `meta/*` (incl. `meta/changelog.md`), `assets/*`, `LAST-UPDATED.md` | `meta` | `never` |

## Provenance (repo-derived docs only)

`repo`, `source`, `commit` (short SHA at read time), `last_sync` (ISO 8601 UTC datetime — never date-only), `stack`. Sync updates only `commit` + `last_sync`; it must not drop other fields.

## `source_globs` (repo-doc / module docs — recommended)

A flow list of source paths the doc covers, **relative to the entry's `source`**, supporting `*`, `?`, `**`:

```yaml
source_globs: [src/api/**, src/routes/**]
```

`gv.py plan` matches these globs against the `last_sync_commit..HEAD` diff so a **sync only regenerates the docs whose source actually changed**. Without it, sync falls back to whole-repo keyword mapping. Never strip it on sync.
