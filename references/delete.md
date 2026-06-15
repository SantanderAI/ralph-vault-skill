# Action: delete

Unregister a repo/subdir from the vault. By default keeps its docs on disk; `--purge` also removes them.

## Do

```bash
# unregister only (docs stay)
python3 scripts/gv.py --vault vault delete --name my-svc

# unregister and delete repos/<name>/ + its repo-card
python3 scripts/gv.py --vault vault delete --name my-svc --purge
```

## What --purge removes

- `repos/<name>/` (the per-repo doc folder).
- `agent-context/repo-cards/<name>.md` (the tier-1 card).

## After

- Run **update**/cross-link so indexes (`index/*`, domain maps) no longer reference the removed repo.
- Run **validate** to catch any now-broken wikilinks pointing at the deleted docs.

## Notes

- Fails if the name is not registered.
- `--purge` is irreversible on disk; rely on git to recover if needed.
