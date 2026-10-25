#!/usr/bin/env bash
# Update one claw's Hermes to the stable release, the hermes-skill procedure
# (2026-10-25, v0.22.2 -> v0.22.5). Run in tmux on the box; log to ~/hermes-upd.log.
set -u
umask 077
H=~/.local/bin/hermes
B=~/backups/hermes-pre-update-2026-10-25
mkdir -p "$B"
echo "== start $(date -u +%FT%TZ) $(hostname)"
cd ~/.hermes/hermes-agent
if [ -n "$(git status --porcelain | grep -v '^??')" ]; then echo "ABORT: dirty checkout"; echo DONE-FAIL; exit 1; fi
echo "before: $($H --version 2>&1 | head -1)"
tar czf "$B/dot-hermes.tgz" --exclude=./hermes-agent --exclude=./tools --exclude=./backups \
  --exclude=./installs --exclude=./cache -C ~/.hermes . && ls -la "$B/dot-hermes.tgz"
cp -p ~/.hermes/config.yaml "$B/config.yaml"
systemctl --user stop hermes-gateway.service
echo "== update $(date -u +%T)"
$H update --yes; rc=$?
echo "== update rc=$rc $(date -u +%T)"
echo "after: $($H --version 2>&1 | head -1)"   # foreground first run of the new revision
systemctl --user start hermes-gateway.service
systemctl --user restart hermes-dashboard.service
sleep 40
echo "gateway=$(systemctl --user is-active hermes-gateway) dashboard=$(systemctl --user is-active hermes-dashboard)"
echo "wrap_response=$($H config get cron.wrap_response 2>&1) interface=$($H config get display.interface 2>&1)"
diff <(grep -v '^\s*#' "$B/config.yaml") <(grep -v '^\s*#' ~/.hermes/config.yaml) | head -40
echo "dirty-after=$(git status --porcelain | grep -v '^??' | wc -l)"
journalctl --user -u hermes-gateway --since "-60 s" --no-pager | grep -E 'ERROR|Traceback|CRITICAL|Connected|connected' | tail -15
[ $rc -eq 0 ] && echo DONE-OK || echo DONE-FAIL
