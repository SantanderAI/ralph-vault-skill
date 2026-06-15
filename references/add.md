# Action: add

Register a repo or subdirectory in the vault config so it gets documented. Does **not** generate docs — that is the **update**/**plan** step.

## Do

```bash
# whole local repo, auto-detect stack
python3 scripts/gv.py --vault vault add --name my-svc --path ../my-svc --stack auto

# remote repo, explicit stack
python3 scripts/gv.py --vault vault add --name billing --url https://git.example/billing.git --stack java

# a subdirectory documented as its own unit
python3 scripts/gv.py --vault vault add --name shared-ui --path ../monorepo/packages/ui --stack frontend --subdir
```

## Arguments

- `--name` (required) — unique id; becomes `repos/<name>/` and the repo-card name.
- `--path` or `--url` — exactly one; the source location. `--path` enables staleness checks.
- `--stack` — `auto` or an id with a matching `assets/stack-tasks/<stack>.md` (java/python/node/go/frontend/scala/generic).
- `--subdir` — mark the source as a subdirectory rather than a full repo.

## After

- `gv.py plan --repo <name>` to emit the ralph task, then run the loop to document it.
- The entry starts at `phase: pending`; it flips to `done` once documented and validated.

## Notes

- Fails if `--name` already exists — delete first or pick another name.
- For an unknown stack, use `generic` (or `auto` to detect at bootstrap).
