# Action: init

Create the vault tier structure + config if missing. **Idempotent** — safe to re-run; never overwrites an existing config or populated files.

## When

- No vault exists yet for the project.
- A partial vault exists and you want to ensure every tier + index is present.

## Do

```bash
python3 scripts/gv.py --vault vault init --project <name>
```

This creates: the 8 tier folders each with a `README.md` index, the root `vault/README.md` (Tier 0 entry point), and `.ralphvault/config.json` with an empty `repos` registry and default `settings`.

## After

- Register what to document with **add** (`references/add.md`).
- Inspect/adjust `settings` in `.ralphvault/config.json` (see `references/config.md`).

## Notes

- `--vault` sets the location (default `vault/`). For a single-repo project documenting itself, `vault/` at the repo root is conventional.
- Re-running reports `created: (nothing — already initialized)` when everything is in place.
