# Action: components

Generate the **components** tier: one file per shared component/library reused across **≥ 2 repos**. Graph content (LLM work) — drive it with the FIXED prompt `assets/prompts/components.md`. `gv.py` only scaffolds the tier and validates frontmatter.

## When

After the owning + consuming repos are bootstrapped. Re-run when a shared library gains/loses consumers.

## Scope boundary (important)

- **Here** (`components/<name>.md`): pieces reused by **two or more** registered repos — a shared UI library, an auth artifact, a common SDK.
- **Not here**: internal, single-repo pieces. Those stay in `repos/<name>/modules/*.md` (`type: module`). Do not duplicate.

## Frontmatter

- `type: component`
- `owner_repo` — wikilink to the repo that publishes it.

## Rules

- **≥ 2 consumers required**; otherwise leave it in the owning repo's `modules/`.
- List consumers as wikilinks; each consumer usually also yields a `code` edge under `relations/`.
- Never copy source code — document the public surface and intent only.
- Suspected-but-unevidenced consumers go to `meta/pending-components.md`.

## After

- `gv.py validate` must report zero errors for the touched files.
