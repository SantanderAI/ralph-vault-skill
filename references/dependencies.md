# Action: dependencies (infrastructure + technologies)

Generate the two **external dependency** tiers, each file carrying a reverse index of the repos that use it. Graph content (LLM work) — drive it with the FIXED prompt `assets/prompts/dependencies.md`. `gv.py` only scaffolds the tiers and validates frontmatter.

## When

After the involved repos are bootstrapped. Re-run when a sync adds/removes an external dependency.

## Which tier

- **`infrastructure/<name>.md`** — a deployable piece the system runs on (broker, cache, database engine, ingress, identity provider, object store). Template: `assets/templates/infrastructure-piece.md`, `type: infrastructure`.
- **`technologies/<name>.md`** — an external SDK/provider/third-party API the code consumes (email/translation/analytics provider, managed AI API, partner API). Template: `assets/templates/technology.md`, `type: technology`.

Rule of thumb: operated/deployed by the team → `infrastructure`; remote third-party consumed via SDK/API → `technologies`.

## Rules

- **Reverse index is mandatory**: list every consuming repo with a wikilink + evidence path.
- One piece per file; never merge two providers.
- **Never paste secrets** — describe the auth mechanism only.
- Suspected-but-unevidenced usage goes to `meta/pending-dependencies.md`.

## After

- `gv.py validate` must report zero errors for the touched files.
