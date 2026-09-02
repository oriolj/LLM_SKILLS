---
name: home-assistant-ops
description: Operate a Home Assistant Core install (Docker, no Supervisor) from the CLI/API without the usual traps — Repairs listing and fix flows over the API, safe Core upgrades (pinned image tag, recorder-DB backup because HA's own backups skip it, entity-diff verification, boot-noise baseline), config-entry-only YAML removal checks, template entities that mirror flaky sources, iOS Live Activities / Android Live Updates via notify payloads (incl. progress extrapolation between slow polls), BLE integrations stuck in setup_error, and a WebSocket helper script. Use when upgrading HA, when Settings → Repairs shows errors, when a legacy `platform:` YAML block is flagged, when a template entity reports a false state during a source outage, when building Live Activities / progress notifications, when a config entry is "loaded" but dead or in setup_error, or when the user mentions Home Assistant, HA Core, Repairs, Live Activities, known_devices.yaml, or the Tesla Fleet polling interval.
---

# Home Assistant Core ops (Docker) — mechanics that bit us

Reference install: Oriol's house (`~/Syncthing/Syncthing-docs/claude_workdirs/homeassistant`,
its `CLAUDE.md` has host paths and the `.env` contract `HA_URL` / `HA_TOKEN` / `HA_SSH_*`).
Everything below is generic to HA Core 2026.x; install-specific facts stay in that repo.

## 1. WebSocket helper — the REST API is not enough

Repairs, entity/config-entry registries and helper creation are WebSocket-only. Drop
`scripts/ha_ws.py` (in this skill) into the project and run with no install step:

```sh
set -a; source .env; set +a
uv run --quiet --with websockets python scripts/ha_ws.py '{"type":"repairs/list_issues"}'
# more: config/entity_registry/get|update|list, config_entries/get, input_boolean/create,
#       input_number/create, input_datetime/create, trace/list
```
Each CLI arg is one command; results print as JSON. Entity registry `update` accepts
`disabled_by: "user" | null` and `new_entity_id`; a re-enabled entity appears after the
integration reloads itself (~30 s).

## 2. Repairs (Settings → Repairs) are sticky records

- **List**: `repairs/list_issues` (WS). Look at `breaks_in_ha_version` before any upgrade.
- **Fixable ones** (`is_fixable: true`, e.g. `automation … service_not_found`) do NOT clear
  when you fix the automation. Run the flow:
  `POST /api/repairs/issues/fix {"handler": "<domain>", "issue_id": "<id>"}` → `flow_id`,
  `step_id: confirm` → `POST /api/repairs/issues/fix/<flow_id> {}` → `create_entry`.
- **Non-fixable boot-time ones** (`platform_integration_no_support_*`, `config_entry_only_*`,
  `deprecated_yaml`) clear only on the next **restart** after the YAML is removed;
  `reload_all` is not enough.
- **Before deleting a `*_only_*` YAML block**, prove the config entry exists
  (`.storage/core.config_entries` → domain, `source: import`) and, for OAuth integrations,
  that the client is in `.storage/application_credentials` ("Import from configuration.yaml").
  Then comment the block out with a dated note instead of deleting silently.
- `deprecated_sensor` (entity X replaced by Y): the replacement is usually in the registry
  `disabled_by: integration`. Disable X (`disabled_by: user`), enable Y (`disabled_by: null`),
  `homeassistant.reload_config_entry` (service accepts `entity_id` or `entry_id`).
- Editing an automation: `POST /api/config/automation/config/<id>` with the full object —
  HA validates, writes `automations.yaml`, reloads. Same for scripts:
  `/api/config/script/config/<script_id>`. Wait ~10 s before checking `/api/states`.

## 3. Upgrading Core in Docker

1. Latest stable = GitHub releases API (`prerelease: false`), not Docker Hub's `stable` tag
   on release day. Monthly `.0` lands the first Wednesday.
2. Read "Backward-incompatible changes" for every skipped month; grep the config for the
   entities named. Compare `custom_components/*/manifest.json` with upstream releases —
   **Spook** tracks Core versions tightly; update it right after (HACS then raises
   `restart_required`).
3. **Pin the tag** (`image: homeassistant/home-assistant:2026.8.3`), never float `:latest`
   (years of floating pulls left 17 dangling 2 GB images; `docker image prune -f` reclaimed
   39 GB). `docker pull` first, stop later.
4. **HA's automatic backups exclude the recorder DB.** With the container stopped, `cp -a`
   `home-assistant_v2.db` (+ `-wal`/`-shm`) and tar the config dir excluding the DB and
   `backups/`. Rollback = old tag + that DB copy (a migrated DB won't open on the older version).
5. `docker compose up -d homeassistant` also **recreates `depends_on` services** (MQTT…) if
   their definitions drifted — expect one reconnect in Zigbee2MQTT.
6. Verify: `/api/config` → `version`, `state: RUNNING` (API answers ~20 s before RUNNING,
   entities keep loading ~2 min — don't diff early). Snapshot `/api/states` before/after; diff
   entity ids and `unavailable` counts; BLE / cloud entities flap for a few minutes after any
   restart. Then `grep " (ERROR|CRITICAL|WARNING) " | sort | uniq -c` against a
   **boot-noise baseline** you keep in the repo, and `repairs/list_issues`.
7. `check_config` (`POST /api/config/core/check_config`) loads integrations → it logs
   "custom integration … not tested" lines; don't mistake them for a boot.

### Seen in 2026.8
- `known_devices.yaml` (legacy device tracker): a subset of entries fails at boot with
  `'consider_home', got None` although the file has no such key and replaying
  `legacy.async_load_config` in the container passes all of them. Workaround that works:
  explicit `consider_home: 0:03:00` on the failing ids
  (`grep -oE "Invalid config for '[^']+' at known_devices"`). Untracked entries create no
  entities, so it is only log noise.
- Tesla Fleet route tracker lost the destination state; `person.*` lost lat/long at home
  (`in_zones` attribute instead).

## 4. Template entities mirroring a flaky source: hold state

`{{ 'locked' if is_state('lock.x','locked') else 'unlocked' }}` turns every source outage
(coordinator timeout → `unavailable` for 30 s) into a confident false `unlocked`. Branch on the
raw state and keep the previous value; `this` is undefined on the first render:

```yaml
state: >-
  {% set s = states('lock.x') %}
  {{ (this.state if this is defined else 'unknown') if s in ['unavailable', 'unknown']
     else ('locked' if s == 'locked' else 'unlocked') }}
```
Test with `POST /api/states/<source>` faking `locked` then `unavailable` (state machine only;
the integration overwrites on its next poll; restore afterwards). Check first that no automation
triggers on the faked states. Same trick tests any automation chain end-to-end without hardware.

Related: state-based template entities boot to `unknown` and render ~60–90 s later on their own;
only treat it as a bug if it persists past ~2 min.

## 5. iOS Live Activities / Android 16 Live Updates

Shipped in the App Store Companion app (verified 2026-09-02 on app 2026.9.0 — the docs/GitHub
still said TestFlight). iOS 17.2+, Core 2026.7+, not on iPad. Plain `notify.mobile_app_*` call:

```yaml
data:
  title: "EV charging"            # REQUIRED on Android, static header on iOS
  message: "62% → 80% · 7.2 kW"
  data:
    tag: ev-charging               # same tag = silent update; clear_notification + tag = end
    live_update: true
    progress: 62
    progress_max: 80
    chronometer: true              # on-device countdown → no pushes needed for the timer
    when: 1756820000               # unix ts it ends at
    notification_icon: mdi:ev-station
    critical_text: "62%"           # Android status-bar chip label (timer replaces it)
```
Limits: Apple ends activities at 8 h; a "push-to-start budget" silently drops too many
*starts* — start once per event (flag `input_boolean`), update via the tag. Samsung: enable
*Live notifications for all apps* in developer options for the chip. Omit empty optional keys
(build the `data:` dict in a template; `null` fields misbehave).

Pattern that worked: a `script.live_activity` (fields tag/title/message/progress/when/icon/
targets list, `repeat.for_each` over notify services) + `script.live_activity_end` (optional
wrap-up push on `<tag>-final`, then `clear_notification`), and per-feature automations on top.

**Progress from a slowly polled source** (Tesla Fleet polls every 600 s — no streaming;
Teslemetry ≈ €3.17/month streams in real time): store `start_distance`, `last_distance`,
`last_poll`, `eta` in `input_*` helpers on each real poll; a `time_pattern: /2` tick pushes
`est = last × (1 − elapsed/(eta − last_poll))`, capped at 99 until a real poll or the end;
the ETA countdown itself runs on the phone via `when`. Gate on a minimum duration (> 40 min)
so short trips don't burn the start budget. Timestamp-class sensors (`device_class: timestamp`)
feed `when` directly via `as_timestamp()`.

## 6. Config entry "dead" vs "not ready"

`ConfigEntryNotReady` → HA retries with backoff. `ConfigEntryError` → state **`setup_error`**,
never retried, no further log lines from the integration — looks like silence. Seen with the
`ef_ble` (EcoFlow BLE) custom integration after "10 unsuccessful attempts" during a flapping
restart: adapter resets can't help; `homeassistant.reload_config_entry` fixes it in seconds.
Check `config_entries/get` (WS, `domain` filter) → `state` + `reason` before touching radios.
Any BLE auto-heal should end with a fire-and-forget entry reload (`script.turn_on` on a helper
script, because `reload_config_entry` has been seen to hang for minutes).

## 7. Small traps

- Nuki coordinator times out a few times a day → lock `unavailable` ~30 s (bridge busy on BLE,
  not fixable from HA). Mirrors must hold state (§4).
- `docker exec … python3 - <<EOF` gives no output; `docker cp` the script in and run it.
- `homeassistant/restart` ≈ 60–120 s; `restart` is required for boot-time Repairs, the first
  entry of a new domain, new `utility_meter`s, custom component updates.
- `POST /api/states` on an integration-backed entity is a test tool only — the next poll wins.
