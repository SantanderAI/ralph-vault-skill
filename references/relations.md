# Action: relations

Generate the **relations** tier: one typed edge per file between two registered repos. This is graph content (LLM work) — drive it with the FIXED prompt `assets/prompts/relations.md` via the ralph loop. `gv.py` does not author edges; it only scaffolds the tier and validates the edge frontmatter.

## When

After the involved repos are bootstrapped (their `repos/<name>/` docs exist). Re-run after a sync that changed integrations/contracts.

## Layout

```
relations/<kind>/<from>_<kind>_<to>.md
```

`<kind>` ∈ `grpc` | `http` | `kafka` | `db` | `code` | `secret` | `apm` | `other`. Subdirs are created on demand by the prompt.

## Edge frontmatter (validator-enforced)

- `from` — wikilink to the caller/producer repo (`[[repos/<from>/README|<from>]]`).
- `to` — wikilink to the callee/consumer repo.
- `relation_type` — one of the kinds above.

The validator errors if any of `from`/`to`/`relation_type` is missing on a non-README file under `relations/`.

## Rules

- Both endpoints must be **registered repos**. Dependencies on infra/providers belong in `infrastructure/`/`technologies/`, not here.
- One direction per file; emit two files for mutual dependencies.
- Cite evidence (source paths) on both ends; verify wikilink targets resolve before writing.
- Suspected-but-unevidenced edges go to `meta/pending-relations.md`.

## After

- `gv.py validate` must report zero errors for the touched edge files.
- The same code dependency that yields a `code` edge often also promotes a shared `components/` entry — see `references/components.md`.
