#!/usr/bin/env bash
# knowhow-skills installer — local copy only.
#
# Copies every skill under ./skills into an agent skill directory.
# This script is deliberately offline: it never downloads anything, never runs
# a remote script, and never modifies a skill it did not install itself.
#
# Usage:
#   ./install.sh                 # -> ~/.workbuddy/skills
#   ./install.sh <target-dir>    # -> <target-dir>
#   ./install.sh --force         # overwrite skills that already exist
#   ./install.sh --list          # show what would be installed

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$HERE/skills"
TARGET="$HOME/.workbuddy/skills"
FORCE=0
LIST_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --list)  LIST_ONLY=1 ;;
    -h|--help)
      sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      [[ "$arg" == -* ]] && { echo "[ERR] unknown option: $arg" >&2; exit 2; }
      TARGET="$arg"
      ;;
  esac
done

[[ -d "$SRC_ROOT" ]] || { echo "[ERR] skills/ not found next to install.sh" >&2; exit 1; }

SKILLS=()
while IFS= read -r d; do
  [[ -f "$d/SKILL.md" ]] && SKILLS+=("$(basename "$d")")
done < <(find "$SRC_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)

[[ ${#SKILLS[@]} -gt 0 ]] || { echo "[ERR] no installable skills found" >&2; exit 1; }

if [[ "$LIST_ONLY" -eq 1 ]]; then
  echo "target: $TARGET"
  printf '  - %s\n' "${SKILLS[@]}"
  exit 0
fi

mkdir -p "$TARGET"
echo "Installing knowhow-skills -> $TARGET"
echo

installed=0; skipped=0
for name in "${SKILLS[@]}"; do
  dest="$TARGET/$name"
  if [[ -e "$dest" && "$FORCE" -ne 1 ]]; then
    echo "  SKIP     $name (already exists; use --force to overwrite)"
    skipped=$((skipped + 1))
    continue
  fi
  rm -rf "$dest"
  cp -R "$SRC_ROOT/$name" "$dest"
  echo "  OK       $name"
  installed=$((installed + 1))
done

echo
echo "installed: $installed   skipped: $skipped"
echo "Restart your agent or start a new conversation to pick up the skills."
