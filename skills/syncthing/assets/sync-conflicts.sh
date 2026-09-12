#!/usr/bin/env bash
# Syncthing conflict triage for Obsidian vaults.
# Read-only except for `clean`, which only ever deletes files you name.
#
#   sync-conflicts.sh list   [dir]              conflicts per share, by device, by kind
#   sync-conflicts.sh notes  [dir]              only .md conflicts (the ones needing a merge)
#   sync-conflicts.sh git    [dir]              conflicts inside .git — the dangerous ones
#   sync-conflicts.sh show   <base.md>          dedupe variants by hash, diff each vs HEAD
#   sync-conflicts.sh verify <merged.md>        assert no line of any variant was lost
#   sync-conflicts.sh devices                   short device ID -> machine name
#
# .stversions is excluded everywhere: it holds archived copies of conflicts.

set -uo pipefail
ROOT="${2:-$HOME/Syncthing}"
CFG="$HOME/.local/state/syncthing/config.xml"
FIND_ARGS=(-name "*sync-conflict*" -not -path "*/.stversions/*")

devices() {
  python3 - "$CFG" <<'PY'
import sys, xml.etree.ElementTree as ET
for d in ET.parse(sys.argv[1]).getroot().findall('device'):
    print(f"  {d.get('id')[:7]} = {d.get('name')}")
PY
}

case "${1:-list}" in
list)
  echo "=== conflicts per share ==="
  for s in "$ROOT"/*/; do
    printf '%5s  %s\n' "$(find "$s" "${FIND_ARGS[@]}" 2>/dev/null | wc -l)" "$s"
  done
  echo; echo "=== by originating device (unresolvable IDs = removed devices, safe to purge) ==="
  find "$ROOT" "${FIND_ARGS[@]}" 2>/dev/null \
    | grep -oP 'sync-conflict-\d{8}-\d{6}-\K[A-Z0-9]{7}' | sort | uniq -c | sort -rn
  echo; echo "=== device map ==="; devices
  ;;
notes)
  echo "=== .md conflicts (union-merge these, never pick one) ==="
  find "$ROOT" -name "*sync-conflict*.md" -not -path "*/.stversions/*" 2>/dev/null | sort
  ;;
git)
  echo "=== conflicts inside .git (divergent history / broken index) ==="
  find "$ROOT" -path "*/.git/*" "${FIND_ARGS[@]}" 2>/dev/null | sort
  echo "Repair: refs/heads/* -> read both SHAs and merge, NEVER reset --hard."
  echo "        .git/index    -> rm -f .git/index && git reset"
  echo "        logs/, COMMIT_EDITMSG -> cosmetic, delete"
  ;;
show)
  b="${2:?usage: show <base.md>}"; d=$(dirname "$b"); n=$(basename "$b" .md)
  cd "$d" || exit 1
  echo "=== variants (identical hashes are duplicate conflicts) ==="
  md5sum "$n".md "$n".sync-conflict-*.md 2>/dev/null
  if git rev-parse --git-dir >/dev/null 2>&1 && git cat-file -e "HEAD:$n.md" 2>/dev/null; then
    echo; echo "=== HEAD is a variant too: it may hold lines every current file lost ==="
    for f in "$n".md "$n".sync-conflict-*.md; do
      [ -e "$f" ] || continue
      echo "--- HEAD vs $f"; git show "HEAD:$n.md" | diff - "$f"
    done
  fi
  ;;
verify)
  m="${2:?usage: verify <merged.md>}"; d=$(dirname "$m"); n=$(basename "$m" .md)
  cd "$d" || exit 1
  # -e is mandatory: markdown list items start with '-' and grep reads them as flags.
  check() { while IFS= read -r l; do
      t=$(echo "$l" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'); [ -z "$t" ] && continue
      grep -qF -e "$t" "$n.md" || echo "MISSING from $1: $t"
    done; }
  for f in "$n".sync-conflict-*.md; do [ -e "$f" ] && check "$f" < "$f"; done
  git rev-parse --git-dir >/dev/null 2>&1 && git show "HEAD:$n.md" 2>/dev/null | check HEAD
  echo "verify done — no MISSING lines above means the union merge is complete"
  ;;
devices) devices ;;
*) sed -n '2,20p' "$0"; exit 1 ;;
esac
