#!/usr/bin/env bash
# Install / update the ralph-vault skill into every skills directory present.
#
# Detects which agent tools are installed (by looking for their skills dir) and
# copies the skill there as a folder named "ralph-vault" (the skill name from
# SKILL.md, not this repo's directory name). Re-running updates an install
# (use --force to overwrite).
#
# Two modes, picked automatically:
#   * local  — run from a clone (SKILL.md sits next to this script): copies it.
#   * remote — piped via curl (no SKILL.md nearby): downloads a tarball from
#              $RALPHVAULT_REPO @ $RALPHVAULT_REF and installs that.
#
# Remote one-liner (set the repo until a default is baked in):
#   RALPHVAULT_REPO=owner/repo \
#     curl -fsSL https://raw.githubusercontent.com/owner/repo/main/install.sh | bash
#
# Usage:
#   ./install.sh                 # copy into every detected skills dir
#   ./install.sh --dest <dir>    # force a specific skills dir (created if missing)
#   ./install.sh --dry-run       # show what would happen, copy nothing
#   ./install.sh --force         # overwrite an existing ralph-vault install
set -euo pipefail

SKILL_NAME="ralph-vault"
# TODO: bake in the real default once the host is decided (e.g. "jairo/ralph-vault").
REPO="${RALPHVAULT_REPO:-OWNER/REPO}"
REF="${RALPHVAULT_REF:-main}"

DRY_RUN=0
FORCE=0
FORCED_DEST=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force)   FORCE=1; shift ;;
    --dest)    FORCED_DEST="${2:?--dest needs a path}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "error: unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Candidate skills directories, keyed off the env/home conventions each tool uses.
CANDIDATES=(
  "${CODEX_HOME:-$HOME/.codex}/skills"
  "$HOME/.claude/skills"
  "$HOME/.gemini/antigravity-cli/skills"
)

# --------------------------------------------------------------------------- #
# Resolve the source tree (local clone or downloaded tarball).
# --------------------------------------------------------------------------- #
CLEANUP=""
trap '[ -n "$CLEANUP" ] && rm -rf "$CLEANUP"' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/SKILL.md" ]; then
  SRC="$SCRIPT_DIR"                                  # local clone
else
  if [ "$REPO" = "OWNER/REPO" ]; then
    echo "error: remote install needs a repo. Set RALPHVAULT_REPO=owner/repo." >&2
    exit 2
  fi
  command -v curl >/dev/null || { echo "error: curl not found" >&2; exit 2; }
  TMP="$(mktemp -d)"; CLEANUP="$TMP"
  url="https://codeload.github.com/$REPO/tar.gz/refs/heads/$REF"
  echo "fetching $REPO@$REF ..."
  curl -fsSL "$url" | tar -xz -C "$TMP"
  SRC="$(find "$TMP" -maxdepth 1 -mindepth 1 -type d | head -n1)"
  [ -f "$SRC/SKILL.md" ] || { echo "error: downloaded tree has no SKILL.md" >&2; exit 1; }
fi

if [ -n "$FORCED_DEST" ]; then
  DESTS=("$FORCED_DEST")
else
  DESTS=()
  for d in "${CANDIDATES[@]}"; do
    [ -d "$d" ] && DESTS+=("$d")
  done
fi

if [ "${#DESTS[@]}" -eq 0 ]; then
  echo "No skills directories detected. Use --dest <dir> to install explicitly." >&2
  echo "Looked for:" >&2
  printf '  %s\n' "${CANDIDATES[@]}" >&2
  exit 1
fi

for dest in "${DESTS[@]}"; do
  target="$dest/$SKILL_NAME"
  if [ -e "$target" ] && [ "$FORCE" -ne 1 ]; then
    echo "skip   $target (exists; use --force to overwrite)"
    continue
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would install -> $target"
    continue
  fi
  mkdir -p "$dest"
  rm -rf "$target"
  cp -R "$SRC" "$target"
  rm -rf "$target/.git"
  echo "installed -> $target"
done
