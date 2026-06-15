#!/usr/bin/env sh
# ralph-vault pre-commit hook — keep the vault structurally valid on every commit,
# and surface (without blocking) any drift from the code.
#
# Install (pick one):
#   cp <skill>/assets/templates/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#   # or, to version it: keep it in the repo and set  git config core.hooksPath <dir>
#
# Override the two paths via env if your layout differs.
set -eu

VAULT="${RALPHVAULT_VAULT:-vault}"        # path to the vault dir
GV="${RALPHVAULT_GV:-scripts/gv.py}"      # path to the skill's gv.py

# Nothing to check until a vault exists.
[ -d "$VAULT" ] || exit 0

# Hard gate: structure must always be valid (frontmatter / wikilinks / no source code).
python3 "$GV" --vault "$VAULT" validate

# Soft check: report missing/pending/stale repos, but do NOT block the commit
# (drift is expected mid-work; CI is where it should hard-fail — see vault-check.yml).
# Make it strict locally by exporting RALPHVAULT_STRICT=1.
if [ "${RALPHVAULT_STRICT:-0}" = "1" ]; then
  python3 "$GV" --vault "$VAULT" check --gate
else
  python3 "$GV" --vault "$VAULT" check || true
fi
