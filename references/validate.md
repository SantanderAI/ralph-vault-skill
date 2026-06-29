# Action: validate

Deterministic gate over the vault. Read-only. Run before committing or marking a repo `done`.

## Do

```bash
python3 scripts/gv.py --vault vault validate
```

Exit code `0` = no errors; `1` = at least one error. Warnings never fail the gate.

## Checks

- **Frontmatter** — every doc (outside `.ralphvault/` and `plan/`) has a YAML block containing the `settings.required_frontmatter` fields. Missing block or field → **error**.
- **Wikilinks** — `[[target]]` / `[[target#anchor|alias]]`:
  - target not found in the vault → **error**.
  - anchor not found in the target's headings → **warning**.
  - intra-doc `[[#anchor]]` not found → **warning**.
- **Token budget** — files whose rough token estimate exceeds `settings.token_budget` → **warning** (`terms.md` exempt).
- **No source code** — the vault must stay at a higher abstraction than code:
  - a fenced block tagged with a programming language (`python`, `js`, `java`, `go`, `sql`, …) → **error**.
  - an untagged/long fence over `code_fence_max_lines` (default 20) → **error** (likely copied source). Tag diagrams/trees as ```` ```text ```` (also `tree`/`mermaid`/`dot`) to exempt them.
- **Source backlink** — a `repo-doc` or `module` that cites no source path (no backticked `path`/`path#Symbol`) → **warning**. Keeps the link back to the original code.
- **Mojibake / encoding** — a doc containing the Unicode replacement char (`�`) or a few unambiguous UTF-8-mis-decoded sequences (e.g. `â€™`, `Ã©`) → **warning**. Advisory only: flags likely encoding corruption, never blocks the gate.

## Fixing

- Broken wikilink target: correct the path, or remove the link if the target was intentionally deleted.
- Broken anchor: match an existing heading verbatim (`grep -E '^#{1,6} ' <target>`), or drop the anchor.
- Missing frontmatter: add the block per `references/vault-structure.md`.
- Over budget: split the file into a sibling or a `modules/` drilldown.
- Code block flagged: remove the source; describe intent/interfaces/structure in prose + tables, and keep only a wikilink/path to the original code as evidence.

## Tuning

Adjust `required_frontmatter`, `token_budget` and `code_fence_max_lines` in `.ralphvault/config.json` (`references/config.md`) per project; the gate honors them. The programming-language list itself is fixed (it encodes the "no code" contract).
