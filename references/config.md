# Config registry — `.ralphvault/config.json`

The single source of truth for what a vault documents. Lives at `<vault>/.ralphvault/config.json`. Created by `gv.py init`; mutated by `gv.py add` / `delete` / `mark-synced`. Edit by hand only for `settings` — in particular, **`phase` and `last_sync_commit` are advanced by `gv.py mark-synced`, not by hand**.

```json
{
  "schema_version": 1,
  "project": "myproj",
  "vault_root": ".",
  "settings": {
    "token_budget": 2000,
    "required_frontmatter": ["type", "load_tier", "schema_version"],
    "glossary": "glossary/terms.md"
  },
  "repos": [
    {
      "name": "my-svc",
      "source": "../my-svc",
      "source_kind": "path",
      "kind": "repo",
      "stack": "python",
      "phase": "pending",
      "last_sync_commit": null
    }
  ]
}
```

## Fields

- **`name`** — unique id; also the `repos/<name>/` folder and repo-card filename.
- **`source`** + **`source_kind`** (`path`|`url`) — where to read the code from. For `path` sources, staleness is **path-aware**: `gv.py` compares the last commit that touched the `source` subtree against `last_sync_commit`, so a `subdir` entry is not flagged when an unrelated part of its monorepo moves.
- **`kind`** — `repo` (whole repository) or `subdir` (a subdirectory documented as a unit).
- **`stack`** — `auto` (detect on first bootstrap) or an explicit id matching an `assets/stack-tasks/<stack>.md`.
- **`phase`** — `pending` → `done`. Set to `done` by the documentation task once the canonical files exist and `validate` passes.
- **`last_sync_commit`** — short SHA last documented; compared against the last commit touching the `source` path to detect drift. Advanced by `gv.py mark-synced`, which also appends the commit→docs mapping to `meta/changelog.md`.

## settings

- **`token_budget`** — soft per-file budget; the validator warns above it (`terms.md` exempt).
- **`required_frontmatter`** — fields the validator enforces as errors.
- **`glossary`** — path to the canonical terms file.
