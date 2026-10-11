---
name: truenas
description: Operate TrueNAS SCALE (25.10 Community Edition) from outside the box — the REST API with an API key (HTTPS only, what answers and what is gone), datasets and passphrase encryption (everything locks at reboot), SMB shares and users, periodic snapshot tasks, catalog and custom apps (Tailscale, Syncthing, Beszel agent, BorgWarehouse) and editing an app's settings through the API. Use when checking or changing anything on truenas-enantena or truenas-personal, when the user mentions TrueNAS, a NAS dataset, a NAS share, a snapshot task, a TrueNAS app or "the NAS", when an app on the NAS misbehaves after an install or a reboot, or before writing a new NAS into hq. Carries the estate's access rules (which box an agent may touch and how), the app.update merge trap, the outdated-catalog-template trap, and the calls the permission classifier refuses.
---

# TrueNAS SCALE — the API, datasets, apps, and the estate's two boxes

Verified on **TrueNAS SCALE 25.10.7** on 2026-10-11 unless a line says
otherwise. State (disks, datasets, apps, addresses) lives in hq
`docs/servers/truenas-enantena.md` and `docs/servers/truenas-personal.md`;
this file is mechanics and rules. Keep both current in the turn a fact is
verified.

## 1. Which box, and what an agent may do

| Box | Scope, tailnet | Agent access |
|---|---|---|
| `truenas-enantena` | company NAS, EnaCast tailnet | TrueNAS API key `claude-hq` in hq `homelab/secrets/truenas-enantena.env` (full admin, **expires 2026-11-11**). **Read freely; change something only when Oriol asks for that change.** |
| `truenas-personal` | family NAS, personal tailnet (reach it on the LAN, `192.168.7.151`) | **No TrueNAS credential, by rule** (hq `shared/docs/backups.md` §2 rule 11). Observe from outside only. Never ask for a key. |

Both: no SSH (service off), and the agent holds each box's **Syncthing**
REST key (`syncthing-truenas-*.env`), which reaches that app only. Mechanics
for those are in the `syncthing` skill.

Observation without a credential: `tailscale ping`, TCP probes
(`</dev/tcp/host/port`), the UI redirect (`curl -sk -o /dev/null -w
'%{http_code} %{redirect_url}'`), the UniFi client list, the Beszel hub's
record, and the Gen8 iLO's unauthenticated `https://<ilo>/xmldata?item=all`
(serial, NIC MACs, firmware).

**The permission classifier refuses some calls even with the key.** Seen
2026-10-11: a first read was refused as a production read until Oriol asked
for a check on the box in plain words; creating a user account
(`POST /user`) was refused as a permission grant even though the mount he
asked for needed it, and went through once he said "create the user
yourself". After one refusal, stop: say what the call is and why it is
needed, and let Oriol either approve that exact step or do it in the UI.
Prepare what he needs meanwhile (a generated password in a secrets file,
never in chat).

A local SMB user through the API: `POST /user` with `username`,
`full_name`, `uid`, `group_create: true`, `groups: [<id of
builtin_users>]`, `password`, `smb: true`, `home: "/var/empty"`, `shell:
"/usr/sbin/nologin"`; a new password later is `PUT /user/id/<id>`
`{"password": …}`. Change the NAS first and write the secrets file only
on a 200, so the two never disagree.

## 2. The REST API

```python
c = httpx.Client(base_url="https://truenas-enantena", verify=False,   # self-signed
                 headers={"Authorization": "Bearer " + key})
c.get("/api/v2.0/system/info")
```

- **HTTPS only. TrueNAS revokes an API key that is sent over plain HTTP.**
- Key format `<id>-<64 chars>`; `GET /api_key` shows name, user, creation
  and expiry (never the secret). Dates come as `{"$date": <ms since epoch>}`.
- REST `/api/v2.0` still answers on 25.10 but is deprecated; some paths
  are already 404 (`update/get_trains`, `zfs/snapshot`,
  `pool/dataset/attachments`). The replacement is JSON-RPC over
  `wss://<host>/api/current` (`auth.login_with_api_key`), not used yet
  here (needs a websocket client).
- A method that takes one argument is a `POST` with that argument as the
  JSON body: `POST /app/config` body `"syncthing"`, `POST /filesystem/stat`
  body `"/mnt/tank/x"`, `POST /filesystem/listdir` body `{"path": …}`,
  `POST /filesystem/getacl` body `{"path": …, "simplified": true,
  "resolve_ids": true}`.
- Long operations return a **job id**; poll
  `GET /core/get_jobs?id=<n>` until `state` is `SUCCESS` or `FAILED`.

Reads that answered (enough to fill a server file):

| What | Call |
|---|---|
| version, model, serial, CPU, RAM, ECC | `GET /system/info` |
| pool health, vdev layout | `GET /pool` |
| disks | `GET /disk` |
| boot pool | `GET /boot/get_state` |
| datasets | `GET /pool/dataset?extra.flat=true`, one: `GET /pool/dataset/id/<name with %2F>` |
| shares, services | `GET /sharing/smb`, `GET /service` |
| users, groups | `GET /user`, `GET /group` (`builtin` flag) |
| snapshot tasks, existing snapshots | `GET /pool/snapshottask`, `GET /pool/snapshot` |
| scrub, replication, cloud sync, rsync | `GET /pool/scrub`, `/replication`, `/cloudsync`, `/rsynctask` |
| apps, one app's settings | `GET /app`, `POST /app/config` |
| where apps and the system dataset live | `GET /docker`, `GET /systemdataset` |
| alerts | `GET /alert/list`, `GET /alertservice` |
| network | `GET /interface`, `GET /network/configuration`, `GET /system/general` (timezone) |

Dataset properties are `{"value": …, "source": …}` objects; `encrypted`,
`locked`, `encryption_root`, `key_loaded` are plain. **Internal datasets
are hidden from `pool/dataset`**: `tank/ix-apps` (apps) and `tank/.system`
exist even though the list does not show them.

## 3. Datasets and encryption

- **A passphrase-encrypted dataset is locked after every reboot** until
  someone unlocks it in the UI. Its SMB share is down and any app whose
  host path sits on it cannot start properly. Key-file encryption unlocks
  at boot, at the price of the key living on the NAS. Ask which one a new
  dataset uses (`key_format`) before promising that anything survives a
  power cut. Losing a passphrase loses the dataset; they are Oriol's and
  never in hq.
- The SMB preset gives `acltype=NFSV4`, `aclmode=RESTRICTED`,
  case-insensitive, and an ACL where `builtin_users` has modify. **A
  local user needs "SMB user" on and membership of `builtin_users`** or
  nobody can log in to the share. A fresh box has only `truenas_admin`
  with SMB off.
- **A share that stops mounting: ask the server what it offers before
  touching the client.** From any machine with the SMB login, no mount and
  no sudo: `USER=<u> PASSWD=<p> smbclient -L //<nas> -m SMB3` (credentials
  through the environment from the secrets file, never argv or a temp
  file), then `smbclient //<nas>/<share> -c ls`. A share missing from the
  list answers `NT_STATUS_BAD_NETWORK_NAME`, and the client's automount
  fails with `mount error(2): No such file or directory` (kernel: `CIFS:
  VFS: cifs_mount failed w/return code = -2`) while the other shares of
  the same box open. Seen 2026-10-11 on truenas-personal for
  `not-important` and `Docs` after a morning reboot: it fits datasets
  left locked, but that cause was not read (no credential on that box).
- Record size is inherited (128K). For large video files set 1M before
  the data lands; it only applies to files written afterwards.
- `statfs` on a ZFS dataset reports that dataset's own bytes, so a pool's
  root shows about 0 used. Anything that reads disk use by `statfs`
  (Beszel) must be given the datasets that hold data, one by one.

## 4. Snapshot tasks

House scheme (both boxes), three recursive tasks on the pool root,
`exclude: ["<pool>/.system"]`, `allow_empty: false`:

| Task | cron | naming schema | keep |
|---|---|---|---|
| hourly | `0 * * * *` | `auto-%Y%m%d.%H%M-2w` | 2 weeks |
| daily | `0 0 * * *` | `auto-%Y%m%d.%H%M-1y` | 1 year |
| monthly | `0 1 1 * *` | `auto-%Y%m%d.%H%M-2y` | 2 years |

`POST /pool/snapshottask` with `dataset`, `recursive`, `exclude`,
`lifetime_value`, `lifetime_unit` (`WEEK`/`YEAR`…), `naming_schema`,
`schedule` (`minute hour dom month dow` + `begin`/`end`), `allow_empty`,
`enabled`. Different naming schemas per task, so each retention prunes
only its own snapshots.

- A new task reads `state: PENDING` until its first run. The schedule is
  in the **box's timezone**, and so are the times other tools print:
  convert before writing "UTC" in a doc (a local 17:43 was logged as UTC
  on 2026-10-11 and a task was thought overdue for two hours).
- Recursive on the pool means **every new dataset is snapshotted by
  default**, the apps dataset included. A scratch dataset, or anything
  that rewrites big files (a Borg repository, renders), must be added to
  the `exclude` of ALL the tasks, or deleted data keeps its space for the
  longest retention.
- Snapshots protect against deletion and overwrite, not against losing
  the pool.

## 5. Apps

Catalog apps publish their own ports (not the upstream defaults), so read
them from `GET /app` → `active_workloads.used_ports`: Syncthing UI 20910
and sync 20978, BorgWarehouse UI 30406 and SSH 30407.

- **An app's host path on a passphrase-encrypted dataset** means the app
  is down after a reboot until the unlock. Syncthing here keeps config,
  identity and folders under one such path. Whether TrueNAS restarts the
  app by itself after the unlock is **not verified**.
- **Tailscale** (`community/tailscale`, host network, kernel mode): the
  *Hostname* field applies on the first join only; with *Auth Once* a
  later change does not (rename in the admin console). Disable key
  expiry in the console. Check which tailnet the admin console is on
  before minting the auth key. More in the `tailscale` skill.
- **Beszel agent**: no catalog app, so a Custom App (Apps → Discover → ⋮
  → *Install via YAML*). Recipe in hq `docs/servers/truenas-personal.md`
  ("Tailscale & Beszel"): host network, `extra_hosts` for the hub name,
  `HUB_URL`, `KEY`, `TOKEN`, and `SYSTEM_NAME` (honoured by agent 0.21:
  the hub named the system from it). The agent dials the hub, so port
  45876 stays closed from outside and that proves nothing; read the hub's
  `systems` table instead. Generate the file into `homelab/secrets/` from
  `beszel.env`, never print it, delete it after Oriol pastes it.
- **Syncthing** (catalog): a forgotten UI login is reset from the app's
  shell with `syncthing cli … config gui user/password set`, after
  `unset STGUIADDRESS` (`syncthing` skill, operations reference).
- **BorgWarehouse on truenas-enantena is the estate's tier-3 backup target**
  (Oriol, 2026-10-11): every server of every scope is to back up there
  with borgmatic, one at a time. Intent, prerequisites and the queue: hq
  `docs/next-steps.md` ("borgmatic on every server"); policy: hq
  `shared/docs/backups.md` tier 3. Before a first client: take
  `tank/borgwarehouse/borg-repository` out of the snapshot tasks, and
  settle passphrase or key file for the dataset (a locked dataset fails
  every client's run). The Borg port answers on the tailnet and the LAN
  only.
- **A catalog template can be older than the app it installs.**
  BorgWarehouse v3.6 (2026-10-11): the template set only the retired
  `NEXTAUTH_SECRET`, so `BETTER_AUTH_URL` was unset, Better Auth issued
  `__Secure-` cookies and the browser rejected them on the plain `http://`
  page (console: *Cookie "__Secure-better-auth.session_token" has been
  rejected for invalid prefix*; login never sticks). Fix = the app's
  *Additional Environment Variables*: `BETTER_AUTH_URL` (scheme and host
  exactly as typed in the browser), `BETTER_AUTH_TRUSTED_ORIGINS` (the
  other addresses), `BETTER_AUTH_SECRET` (else a new one at every restart
  logs everyone out), `FQDN`, `SSH_SERVER_PORT`. Set that way on
  truenas-enantena, the login worked (confirmed by Oriol, 2026-10-11).
  When an app half-works
  after install, compare the template's environment
  (`github.com/truenas/apps`, `ix-dev/<train>/<app>/templates/`) with the
  upstream project's own `.env.sample`.

### Editing an app through the API

```python
cur = c.post("/api/v2.0/app/config", json="borgwarehouse").json()
r = c.put("/api/v2.0/app/id/borgwarehouse",
          json={"values": {"borg": {"additional_envs": [{"name": "X", "value": "y"}]}}})
job = r.json()          # poll core/get_jobs?id=<job>
```

- **`app.update` replaces each TOP-LEVEL group it is given** (`borg`,
  `network`, `storage`…), it does not merge inside one. Read the current
  config first, send the WHOLE group you change with your edit applied,
  and leave the other groups out. Afterwards read the config back and
  compare every other group with the copy from before.
- The update redeploys the app (containers recreated). Verify behaviour,
  not the job state: the version endpoint, then a request that exercises
  the thing fixed. A sign-in with a user that does not exist is a clean
  401 when the origin settings are right, but a few of them in a row hit
  the app's rate limit (429), and a real login is still the owner's to
  confirm.
- Secret values go from a `homelab/secrets/` file into the request,
  never through chat or a log line.

## 6. Clients

The dev machines mount SMB shares through hq `homelab/ansible`
`roles/nas` (`--tags nas`), one entry of `nas_servers` per NAS, systemd
automounts on Linux and autofs on macOS. **Both boxes are addressed by
their LAN IP** (Oriol, 2026-10-11): the tailnet name works at home and
away, but the bytes then ride WireGuard even on the direct LAN path, and
on truenas-enantena's two-thread CPU that measured 49.9 / 43.5 MB/s
write / read against about 149 / 63 by LAN address. A LAN-IP mount needs
the address pinned on the gateway, and away from home the home subnet
route. Measure with `oj-nas-speed -N <nas>` (hq dotfiles `local-bin`),
on an idle NAS, not across the hourly snapshot. Details and the per-option reasons: hq
`docs/servers/truenas-personal.md` ("Laptop clients") and
`homelab/ansible/CLAUDE.md`.

## 7. Writing a new NAS into hq

1. Server file from `docs/servers/_template.md`; omit what was not read.
   A serial from `system/info` settles "which chassis is this" (a refit
   box keeps its serial: merge with the old file instead of adding one).
2. Datasets with encryption type, shares, snapshot tasks, apps with
   their ports, and what is NOT done (second copy, fixed IP, uptime
   check, backup-register note).
3. Secrets: one file per credential in `homelab/secrets/`, catalog entry,
   `USER_TODO.md` for the encryption (`secrets-in-git` skill).
4. Fixed IP and local DNS name on the gateway (`unifi` skill): a NAS on a
   DHCP lease moves.
5. Who can reach it: every node of its tailnet unless an ACL says
   otherwise, and no agent can read the ACL policy.
