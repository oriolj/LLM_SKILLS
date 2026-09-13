---
name: unifi
description: Operate a UniFi gateway (Cloud Gateway Fiber/Max/Ultra, Dream Machine, UniFi OS consoles) from the CLI/API without the usual traps — the three API layers behind the UniFi OS proxy (Integration v1, classic `api/s/<site>`, v2) and which one carries what, X-API-KEY auth vs local-admin login, DHCP reservations (fixed IP + local DNS record on the client object), DHCP range/lease/domain on the network object, static DNS records, port forwards, dynamic DNS, backups, the setup-wizard API (ISP VLAN tag, the "302 until setup completes" gotcha), full-object PUT and read-before-write doctrine, and what a UniFi gateway cannot do (Tailscale, recursive DNS). Use when configuring or auditing the home UCG-Fiber (192.168.7.1), migrating a router to UniFi, restoring DHCP leases/reservations, adding a port forward or DDNS, when `dig` against the gateway returns no local names or PTRs, when a UniFi API call returns 401/404, or when the user mentions UniFi, Ubiquiti, UCG, UDM, Dream Machine, UniFi OS, fixed IP, DHCP reservation, or the Network application.
---

# UniFi gateways — API layers, reservations, and the traps

Estate context: one UniFi console, the **UniFi Cloud Gateway Fiber** that
replaced OPNsense as the home router on 2026-09-12 (homelab scope,
`https://192.168.7.1`, Oriol's personal UI account). Everything specific
to that LAN lives in hq: the home-network overview
`homelab/docs/network/README.md`, the server file
`docs/servers/ucg-fiber.md`, the migration status page
`ucg-fiber-status.md` (done / pending / problems, kept current in the
same turn as any change), the runbook `ucg-fiber-migration.md`,
`lan-address-book.md`, `ucg-fiber-reservations.csv`, and the applier
`homelab/tools/unifi-fixed-ips.py`. This skill holds the mechanics that
outlive that migration — **and every new fact learned on the console
is written here in the same turn** (Oriol, 2026-09-12). Facts marked *(verified YYYY-MM-DD)* were seen on
the live console; anything else comes from the references in section 9
and must be confirmed with a GET before it is relied on for a write.

## 1. Credentials

- **API key** — minted in the **Network application's** settings:
  `https://<console>/network/default/settings/control-plane/integrations`
  → Create API Key *(verified 2026-09-12 on a UCG-Fiber: the UniFi
  OS-level Settings → Control Plane had no Integrations tab; the Network
  app's Control Plane does — two menus share the name, send the user the
  URL, not the breadcrumb)*. Stored in hq as
  `homelab/secrets/unifi.env` (`UNIFI_URL`, `UNIFI_API_KEY`; age
  store, catalogued in hq's root `CLAUDE.md`). Read a key with
  `grep '^UNIFI_API_KEY=' file | cut -d= -f2-`, never `source`, never
  print it. Sent as the header `X-API-KEY` (case-insensitive). No CSRF
  token, no cookie. A **401 means wrong or revoked key: ask Oriol, never
  retry around it**.
- **Local admin login** — `POST /api/auth/login` with
  `{"username","password"}` returns a `TOKEN` cookie and an
  `X-Csrf-Token` header that must be echoed on writes. Only needed for
  WebSocket streams and a few UniFi OS endpoints. **UI (SSO/MFA)
  accounts cannot log in this way**; a dedicated local admin can. Prefer
  the API key; if a local admin is ever created for agents, it goes in
  the same env file as `UNIFI_USERNAME` / `UNIFI_PASSWORD`.
- **Site Manager (cloud) key** — a different key from unifi.ui.com for
  multi-site/CGNAT cases. Not used on the estate.
- The console's certificate is self-signed: `curl -k`, `verify=False`.

## 2. The three API layers behind the UniFi OS proxy

All local calls go through the UniFi OS proxy on port 443. The path
prefix decides which application and which generation of API answers:

| Layer | Prefix | Shape | What it carries |
|---|---|---|---|
| **UniFi OS** | `/api/…` | plain JSON | console facts (`/api/system` — unauthenticated, *(verified 2026-09-12)*: `name`, `hardware.shortname`, `mac`, `deviceState`, `hasInternet`, `cloudConnected`, `remoteAccessEnabled`, `isSsoEnabled`), the setup wizard (`/api/system/dhcp`, §6), backups, users |
| **Integration v1** | `/proxy/network/integration/v1/` | `{offset,limit,count,totalCount,data:[…]}` (paginate with `?offset=N&limit=…`) | the official, OpenAPI-documented API: sites (UUIDs), devices, clients, firewall zones/policies, networks, WLANs, port forwards, DNS on recent versions. Read-mostly; writes exist for some objects on Network 9.x+ and 404 on older firmware |
| **Classic** | `/proxy/network/api/s/<site>/` (site short name, `default`) | `{"meta":{"rc":"ok"},"data":[…]}` | the broadest surface: `rest/user` (clients incl. **fixed IP and local DNS record**), `rest/networkconf` (DHCP range/lease/domain), `rest/portforward`, `rest/dynamicdns`, `rest/wlanconf`, `stat/sta`, `stat/health`, `stat/device`, `cmd/stamgr`, `cmd/devmgr` |
| **v2** | `/proxy/network/v2/api/site/<site>/` | plain JSON | `static-dns` (DNS records), `trafficrules`, `system-log/all` (events; replaces the classic `stat/event` on Network 10.x) |

The same API key authenticates all four *(verified 2026-09-12: reads on
Integration and classic, `PUT`/`POST rest/user`, `PUT rest/networkconf`
and `POST v2 static-dns` all succeeded with only `X-API-KEY`)*. Find the site
UUID with `GET /proxy/network/integration/v1/sites` (`id` = UUID,
`internalReference` = classic short name).

The skill's `scripts/unifi_api.py` is a raw client for all layers:

```sh
scripts/unifi_api.py GET  classic rest/networkconf
scripts/unifi_api.py GET  integration sites
scripts/unifi_api.py PUT  classic rest/user/<_id> '{"use_fixedip":true,"fixed_ip":"192.168.7.229","network_id":"<net>"}'
scripts/unifi_api.py POST v2 static-dns '{"record_type":"A","key":"hass.localdomain","value":"192.168.7.105","enabled":true}'
```

It reads `UNIFI_URL` / `UNIFI_API_KEY` from the environment or from
`--env <file>` (default: hq's `homelab/secrets/unifi.env`).

## 3. Doctrine — the rules that keep a gateway administrable

1. **Read before write, dry-run before apply, verify with a fresh read.**
   Controllers echo back configuration they never applied (community
   finding, not seen here yet); a `200` is not proof. Re-GET the object
   and, for DHCP/DNS, test from a client (`dig`, `ip a`).
2. **Classic `rest/*` PUTs replace the object.** Fetch the full object,
   change the fields, PUT the whole thing back. Partial PUTs on
   `portconf` (switch ports) and `networkconf` are known to wipe the
   fields you left out. `rest/user` accepts partial bodies in practice,
   but send the full set of related fields anyway (`use_fixedip`,
   `fixed_ip`, `network_id` together).
3. **Never change the network you are connected through** (subnet,
   VLAN, DHCP off) from a client on that network without console or
   physical access to roll back. The wizard and `rest/networkconf` will
   happily cut the branch you sit on.
4. **Anything that disconnects clients is confirmed in conversation
   first**: device restart, PoE port cycle, SSID/VLAN changes, firewall
   policy changes. State the exact impact, get a yes, then act.
5. **Snapshot before a batch of writes**: download a `.unf` backup
   (Settings → System → Backups, or the UniFi OS backup API) and keep it
   in `homelab/secrets/` (it contains Wi-Fi passphrases and keys).
6. **Two firewall systems coexist** on Network 9.x/10.x: legacy rules
   (`rest/firewallrule`) and zone-based policies (Integration
   `firewall/policies`). A new zone defaults to *block* against
   Internal in both directions; a bad policy does not error, it just
   locks you out. Stage allow policies before restrictive ones.
7. Keep the credential out of the agent's context: pass it via env or
   header from the file, never paste it into a prompt or a commit.

## 4. DHCP reservations — restoring leases after a router swap

A fixed IP is a property of the **client** (`rest/user`), not of the
network. Field names *(verified 2026-09-12: 15 reservations applied with
exactly these fields, partial PUT bodies accepted)*:

| Field | Meaning |
|---|---|
| `mac` | the client (lower-case, colon-separated) |
| `use_fixedip` / `fixed_ip` | reservation on/off and the address |
| `network_id` | `_id` of the network object (`rest/networkconf`) the address belongs to — required |
| `name` | display name (also what the UI shows) |
| `local_dns_record_enabled` / `local_dns_record` | serve `<record>` (and `<record>.<domain>`) for this client — the per-client "Local DNS Record" toggle |

Mechanics:

- Clients the controller has already seen exist in `rest/user`; find the
  `_id` by MAC and `PUT rest/user/<_id>`. A client never seen (a NAS that
  was off during the swap) is created with `POST rest/user` carrying the
  MAC and the same fields.
- **A reservation does not move a device.** The client keeps its current
  lease until it renews or reconnects. To move it now: power-cycle it,
  re-plug the cable, or shorten the lease. After the OPNsense → UCG-Fiber
  cutover four devices had drifted (Nuki bridge, Nest Hub, Mac mini,
  Enphase envoy) because the reservations were not there when they
  leased *(2026-09-12)*.
- **Reserve the NIC that is plugged in.** The minisforum's OPNsense
  reservation targeted its onboard NIC while the cable was in a second
  adapter, so it never got the address under either router. Check
  `ip -br link` on the host before copying a MAC from an old config.
- Fixed IPs may sit inside the DHCP range; UniFi does not require them
  to be outside it *(the estate keeps UniFi's default `.6`–`.254` and
  reserves inside it, Oriol 2026-09-12)*.
- **Removing a reservation / a client**: `DELETE rest/user/<_id>`
  answers 404 *(verified 2026-09-12)*. Clear the fields with
  `PUT rest/user/<_id> {"use_fixedip":false,"local_dns_record_enabled":false}`,
  then drop the entry with `POST cmd/stamgr {"cmd":"forget-sta","macs":[…]}`.
  Delete the matching `static-dns` record separately (`DELETE
  static-dns/<_id>` works).
- **`api.err.FixedIpAlreadyUsedByClient`** (HTTP 400 on the PUT): the
  address is held by another client's **live lease**, not by a
  reservation — the error names that client's MAC. Wait for its renewal,
  move it, or pick another address; an applier must log the failure and
  continue with the next row instead of aborting *(2026-09-12: the Mac
  mini's historical `.67` and the fallback `.66` were both live leases of
  other devices)*.
- **Local DNS record semantics** *(verified 2026-09-12)*: the record is
  served exactly as written — `nuc8i7` answers `nuc8i7` and the PTR
  becomes `nuc8i7.`; `nuc8i7.localdomain` answers the FQDN and the PTR
  becomes `nuc8i7.localdomain.` — but not both. The network's Domain
  Name is **not** appended to it. For bare **and** FQDN, keep the client
  record bare and add a v2 `static-dns` A record for the FQDN (§5).
  Changes take ~10 s to reach dnsmasq; a `dig` right after the PUT still
  shows the old answer.
- **Dynamic leases get no PTR** on the UCG-Fiber *(verified 2026-09-12:
  `dig -x` on four dynamic leases empty, forward lookup of the DHCP
  hostname works for some)*. Anything that names devices by reverse DNS
  (NetAlertX's DIGSCAN) only sees the reserved hosts.
- The estate's plan file format and applier:
  `homelab/tools/unifi-fixed-ips.py --plan <csv>` (dry run) then
  `--apply`; rows are `mac,ip,name[,dns]`. It also sets the range:
  `--network --dhcp-range 192.168.7.10 192.168.7.245 --apply`.

DHCP range, lease and domain live on the network object
(`rest/networkconf`, the `purpose: corporate` entry named *Default*):
`dhcpd_start`, `dhcpd_stop`, `dhcpd_leasetime` (seconds), `domain_name`,
`dhcpd_dns_enabled` + `dhcpd_dns_1..4`. **UniFi's default range is
`.6`–`.254`** — a migration that planned `.10`–`.245` must set it
explicitly; the wizard does not ask *(seen 2026-09-12: fresh leases at
`.6` and `.9`)*.

## 5. DNS on a UniFi gateway

- The gateway runs dnsmasq that **forwards** to the WAN resolvers
  (Settings → Internet → WAN → DNS server; the wizard defaults to
  `1.1.1.1`). There is no recursive resolver; if recursion or custom
  blocklists matter, run Unbound on a LAN host and point the network's
  DHCP DNS at it. Ad-blocking exists as a per-network toggle ("Ad
  Blocking" / DNS Shield on recent versions).
- DHCP lease hostnames resolve as `<host>` and `<host>.<domain_name>`
  once the network's Domain Name is set. Static names come from the
  per-client Local DNS Record (§4) or from **DNS records**:
  `GET/POST /proxy/network/v2/api/site/default/static-dns` with the
  **full** body — the short one returns 400 *(verified 2026-09-12)*:
  `{"record_type":"A","key":"hass.localdomain","value":"192.168.7.105","enabled":true,"ttl":0,"port":0,"priority":0,"weight":0}`
  (types A, AAAA, CNAME, MX, TXT, SRV, NS on Network 8.x+; **update =
  delete + create**; `DELETE static-dns/<_id>`). The Integration API
  mirrors them read-only at `sites/<uuid>/dns-records`. `.local` is mDNS
  territory and is not served.
- **Reverse DNS (PTR) is not guaranteed.** Tools that name LAN devices
  through `dig -x` against the gateway (NetAlertX's DIGSCAN on the
  estate) lose names when PTR answers are empty. Test on day one:

  ```sh
  dig +short nuc8i7.localdomain @192.168.7.1     # forward, local
  dig +short -x 192.168.7.229 @192.168.7.1       # reverse
  ```

  Right after the cutover both were empty because no reservation or
  record existed yet *(2026-09-12)*; re-test after applying them and
  record the outcome in the project's network docs.

## 6. UniFi OS: setup wizard, console facts, backups

- `GET https://<console>/api/system` works **without auth** and is the
  fastest way to tell what you are talking to and whether it is set up
  (`deviceState`, `isSetup`, `hasInternet`, `mac`, hardware short name)
  *(verified 2026-09-12)*. **Versions** are not there: classic
  `stat/sysinfo` gives the Network app (`version`, e.g. `10.6.101`) and
  UniFi OS (`console_display_version`, `udm_version`); `stat/device`
  gives the gateway's firmware, kernel and **`port_table`** (which ports
  are up, at what speed, PoE) *(verified 2026-09-12: UniFi OS 5.1.33,
  Network 10.6.101 — the firmware every note in this skill was checked
  on)*.
- **Adoption**: a UniFi switch/AP never "just appears". A factory-default
  unit on the same L2 shows in `stat/device` with `adopted: false`
  (UI: Devices → pending) and needs *Adopt*; a unit previously adopted
  by another controller keeps informing that one and shows nothing (or
  "managed by other") until it is factory-reset (hold reset ~10 s) or
  re-pointed over SSH (`ssh ubnt@<ip>`, then `set-inform
  http://<gateway>:8080/inform`). A device that is not even a DHCP client
  (no Ubiquiti OUI in `rest/user`/`stat/sta`) is unpowered, unplugged, or
  holding a static IP in another subnet (UniFi fallback `192.168.1.20`).
- **Wizard WAN step over the API** *(verified 2026-09-12 on a
  factory-fresh UCG-Fiber)*: an ISP that needs a VLAN tag (Yoigo/MásMóvil
  fiber in Spain: VLAN 20, DHCP, no PPPoE) makes the wizard stop at *No
  Internet Detected*. The fix is under *Other Configuration Options*, or
  the call the wizard makes:

  ```sh
  curl -sk -X POST https://192.168.1.1/api/system/dhcp \
    -H 'content-type: application/json' \
    -d '{"wan":"WAN","mac_override_enabled":false,"dns1":"1.1.1.1","vlan_enabled":true,"vlanId":20}'
  ```

  Until the wizard is completed the gateway does **not** route LAN
  clients: every outbound request gets an nginx `302` to the wizard.
  "No internet on the laptop" at that stage is normal, not a WAN fault.
  Completing the wizard needs the owner's UI account (or *Set Up the
  Console Offline* with a local admin) — an agent stops there.
- Backups: Settings → System → Backups (auto backup + optional cloud
  backup). The `.unf` file is the whole console config including
  passphrases; store it in the encrypted secrets dir, never in docs.
  Download after every configuration batch, and before firmware
  updates.
- Firmware: update UniFi OS and the Network application before
  configuring a new console; DNS records, zone firewall and the VPN
  server depend on recent versions, and Network 10.x removed classic
  endpoints (`stat/event`, `stat/alarm`, `rest/vpnclient`,
  `rest/vpnserver` — use the v2 system-log and VPN APIs).

## 6b. Reading the physical layer — `stat/device.port_table`

The controller is a free link tester; read it before touching cables
*(all verified 2026-09-13 on the UCG-Fiber + USW Flex 2.5G 5, Network
10.6.101)*:

- `stat/device[].port_table[]` per port: `up`, `speed`, `full_duplex`,
  `autoneg`, `media`, `poe_enable`/`poe_power`, `stp_state`,
  `rx_bytes`/`tx_bytes`, `rx_packets`/`tx_packets`, `rx_errors`,
  `rx_dropped`/`tx_dropped`, `tx_broadcast`/`tx_multicast`, and
  **`uptime` = seconds since the link last came up** — compare with the
  device's own `uptime` to spot a link that flapped after boot.
  `port_table[].mac_table` is empty on these models; use `stat/sta`
  `sw_mac`/`sw_port` to see what hangs off a port instead.
- **Link up at 1000 + `rx_packets: 0` + `rx_errors: 0`** while `tx_*`
  grows (the switch flooding broadcast at it) = the far end is silent:
  the classic **two-pair cable** (pairs 4-5/7-8 open; autoneg on pairs
  1-2/3-6 still agrees on gigabit) or a peer holding its port blocked.
  Discriminator: force the port to **100 Mbps FDX** — traffic flows on a
  two-pair cable, still nothing if the peer is silent. A corrupt cable
  shows `rx_errors` instead of silence. *(hq case 2026-09-13, the
  2nd-floor Deco: forced to 100 → still 0 rx → silent peer, cable
  theory dropped; write-up in hq `homelab/docs/network/deco-backhaul.md`.)*
- **`stat/sta` can list a client the LAN cannot reach.** A wired entry
  with `sw_port` set, `last_seen` = now, but `rx_bytes`/`tx_bytes` null
  and no ARP reply means the gateway's forwarding table learned the MAC
  on that port (the device emits *something* — discovery/loop-detection
  frames) while the device has no working IP path. **Always ping before
  calling a client "online"**, and read `sw_port` as "where its frames
  enter", which for a mesh AP in backhaul detection can be a port nobody
  expected *(verified 2026-09-13: Deco 2/3 "online" on UCG port 3, 100 %
  ping loss)*.
- **Group `stat/sta` entries by `last_seen` to reconstruct a transient
  path.** Clients bridged by a flapping AP/switch all age out at the
  same second; the `sw_port` they share names the port that path entered
  through, and the set of hostnames names the floor/room. This is how a
  four-minute backhaul window was pinned to a specific gateway port
  after the fact *(2026-09-13; `jq` with `now - .last_seen` per client)*.
- **A silent link partner that stays silent at 100 Mbps** is, in a
  Deco/mesh house, most often an AP's LAN port **blocked by its own
  loop protection** because a second wired path reaches the same LAN.
  Trace cables before replacing anything; an unplug-and-watch loop
  (`stat/sta` `sw_port` + `ping`) names the cable.
- `rx_dropped` on a gateway port carrying hundreds of GB = congestion at
  that port's speed, not a cable problem.
- **Clients behind a third-party AP or unmanaged switch all appear as
  `is_wired: true` on the AP's/switch's port** — the controller only
  sees its own cable. 40 "wired" clients on one 1G port = an AP.
- The Flex Mini 2.5G can be **PoE-powered by the gateway** (UCG port 4
  PoE+, 3.4 W idle): a PoE renegotiation reboots the switch. Device
  fields `startup_timestamp`, `adopted_at`, `provisioned_at` date the
  last boot and adoption.
- **Port overrides (speed, PoE, profile) are UI-only with the API key on
  Network 10.6**: `rest/device` and `rest/device/<_id|mac>` answer 404,
  `rest/portconf` is empty; `stat/device/<mac>` reads fine but
  `port_overrides` comes back `null`. The Integration API has no port
  writes either. Send the user to Devices → switch → Ports → port → Link
  speed. A **Cable Test** button exists on some switch models under the
  port's settings (TDR: open/short + distance; not a certified tester —
  [community thread](https://community.ui.com/questions/Interpreting-Unifi-Switch-Cable-Test/14d0604c-8f82-4a78-b954-09e3a27067db)).
- `v2 system-log/all` with `{"pageNumber":0,"pageSize":60,"categories":[…]}`
  returned nothing on 10.6.101 — body shape unknown; do not rely on it
  for link history yet.

- **Laptop substitution is the decisive physical-layer test.** When a
  device on a run shows link-up/zero-rx, put a laptop on the same jack
  and patch: rx flowing with `rx_errors: 0` clears the run, jack, patch
  and switch port in one move and leaves only the device *(2026-09-13:
  164 MB / 0 errors for the laptop, 0 frames for the Deco on the same
  cable; the Deco was replaced and the port carried 300 k packets in 10
  minutes)*. Do this before any cable re-termination.
- **UniFi APs in the API** (`stat/device` type `uap`, verified 2026-09-13
  on a U7 Pro): `uplink.uplink_remote_port`/`speed` name the switch port
  and negotiated speed (`1000` for a 2.5G AP means **something on the
  path is 1G** — an unmanaged switch in between is invisible to the
  controller, so ask what sits at the jack before blaming the cable;
  2026-09-13: a 1G PoE switch powering the AP), `num_sta`, `satisfaction`,
  `radio_table` (bands `ng`/`na`/`6e`, channel, width) and
  `radio_table_stats` (channel in use, `num_sta`, `cu_total` channel
  utilisation, `tx_power`). Clients carry `ap_mac`, `essid`, `radio`,
  `rssi`, `satisfaction`. WLANs: `rest/wlanconf` (`wlan_bands`,
  `security`, `wpa3_transition`, `fast_roaming_enabled` = 802.11r,
  `bss_transition` = 802.11v). A PoE AP on a **USW Flex Mini 2.5G**
  needs an injector — that switch has no PoE output (`port_poe: false`
  on every port).

- **"Wi-Fi is slow" triage, in this order** *(2026-09-13, a Wi-Fi 7
  laptop reporting 43 Mbps)*: (1) **the ISP line from the gateway
  itself** — `POST cmd/devmgr {"cmd":"speedtest"}` (returns `[]`
  immediately), wait ~45 s, read `stat/device` type `udm` →
  `["speedtest-status"]` (`xput_download`/`xput_upload` in Mbps,
  `latency`, `server.city`, `rundate`; 944/876 to Barcelona on the Yoigo
  line); (2) **a wired client** through the same switches (`speedtest-cli
  --simple`; python speedtest under-reports on gigabit, curl to a single
  CDN file is worse — Cloudflare's `__down` answers 403 to curl); (3) **the
  client's association** in `stat/sta`: `radio` (`6e`/`na`/`ng`),
  `radio_proto` (`be` = Wi-Fi 7), `channel`, `signal` dBm, `tx_rate`/`rx_rate`
  (negotiated PHY rate in kbps — 2 161 800 = 2.16 Gbps), `satisfaction`,
  `tx_retries` vs `wifi_tx_attempts`; (4) **the AP's uplink rate right
  now**: `stat/device` uap `.uplink["rx_bytes-r"]` in B/s — if it is
  pulling 50 MB/s while the user sees 43 Mbps, the radio path is not the
  bottleneck. When (1)–(4) are all good the cause is on the client: a VPN
  (AirVPN/WireGuard caps in exactly that range), the test server, NIC
  power save, or the driver — check with `iw dev <if> link` (bitrates),
  `iw dev <if> get power_save`, `nmcli con show --active`. **Reading
  power save on Intel Wi-Fi 7 (BE2xx, `iwlmld`)**: `iw … get power_save`
  is the live 802.11 state; `nmcli -f 802-11-wireless.powersave con show
  <profile>` `0` = driver decides, `2` = disabled, `3` = enabled (the
  per-profile override that survives reconnects);
  `/sys/module/iwlwifi/parameters/power_save` is the *device* power
  mode, unrelated to the link, `N` is normal; the real knob is
  `/sys/module/iwlmld/parameters/power_scheme` — `1` CAM (never sleep),
  `2` BPS balanced (default), `3` LP aggressive — set via
  `/etc/modprobe.d/iwlmld.conf` (`options iwlmld power_scheme=1`), and
  the module is `iwlmld`, not the `iwlmvm` most guides name.
- **Separate radio from client with a LAN iperf3** before blaming the AP:
  `iperf3 -s -D` on a wired 2.5G host, then from the client `iperf3 -c
  <host>` (client TX) and `-R` (client RX). A negotiated 2.4 Gbps link
  giving **18 Mbps client→AP and 250 Mbps with hundreds of retransmits
  AP→client** while the AP reports satisfaction 99 is the client's
  transmit path (driver/firmware/power save), not the AP *(2026-09-13,
  Framework 13 with Intel BE211 on the new `iwlmld` op mode, kernel
  7.3.0-rc2, firmware c107 missing → c106 loaded)*. Over SSH you can
  read `iw dev <if> link|station dump|get power_save` and the kernel
  log, but **polkit refuses `nmcli con up` and `iw … set power_save`
  needs root** — band/power-save experiments need the user at the
  laptop. Workstations' ufw here admits SSH only on `tailscale0`, so use
  the MagicDNS name, not the LAN IP.
- **The reference-client test ends the argument.** A second capable
  device on the *same* radio (a Wi-Fi 6E/7 phone on the 6 GHz SSID)
  running a speed test: line rate there = the AP and its path are fine,
  and everything left is the slow client's own stack *(2026-09-13: Fold7
  799/922 on the radio where the laptop got 40/20)*. Then check the
  client's kernel/firmware pairing: `pacman -Q linux* linux-firmware`,
  `uname -r`, `ls /usr/lib/firmware/iwlwifi-*` vs the ucode the kernel
  log says it loaded — a firmware package installed *after* boot means
  the driver is still running the old ucode until a reboot *(this was
  the whole fault on 2026-09-13: `linux-firmware` upgraded while the
  laptop stayed up → BE211 on c106 with the new `iwlmld` driver → 18 Mbps
  TX at a 2.6 Gbps PHY rate; after the reboot c107 loaded and the same
  kernel gave 457/401. Rebooting, not changing the kernel, fixed it —
  `uname -r` was unchanged.)*
- **Judge Wi-Fi speed against the negotiated rate, not the box.** Real
  TCP throughput is ~50–60 % of the PHY rate `iw dev <if> link` /
  `stat/sta` report (2 streams MCS 11: 40 MHz ≈ 574 → ~300 Mbps; 80 MHz
  ≈ 1201 → ~650; 160 MHz ≈ 2402 → wire-limited on a 1 Gbps uplink). A
  client at 60 % of its PHY rate is healthy; one at 1 % has a client-side
  fault *(2026-09-13: 536/655 LAN on 5 GHz 80 MHz = fine; 18 Mbps on a
  2.6 Gbps PHY = the stale-firmware bug)*. Internet speed tests sit below
  the LAN figure by the server's and the tool's own variance.
- **Radio config review points** (`stat/device` uap `radio_table`): 2.4 GHz
  20 MHz is right; **5 GHz at `ht: 40` is the conservative default — 80 MHz
  doubles 5 GHz throughput** for Wi-Fi 6/7 clients and is the one change
  worth making on a lightly loaded AP (UI: Devices → AP → Radios; not
  writable with the API key on 10.6); 6 GHz 160 MHz with PMF required is
  the correct 6E/7 setup; `mlo_enabled` on the WLAN needs a multi-band
  WLAN (a 6 GHz-only SSID cannot do MLO). **320 MHz on 6 GHz**: the U7
  Pro supports it and ETSI's lower 6 GHz (Spain, country `724`) fits one
  320 MHz channel, but it only pays once the AP's *wired* uplink exceeds
  the client's current PHY rate — behind a 1 Gbps switch it changes
  nothing and halves per-subcarrier power (~3 dB, some range). Decide it
  with the uplink upgrade, not before.
- **Radio widths/channels/power are UI-only on Network 10.6 with an API
  key** *(verified 2026-09-13)*: Integration `PATCH sites/<id>/devices/<id>`
  → 405, classic `rest/device` → 404; Integration `GET
  sites/<id>/devices/<id>` does return `interfaces.radios[]`
  (`frequencyGHz`, `channelWidthMHz`, `channel`, `wlanStandard`) for
  reading. `GET integration/v1/info` gives `applicationVersion`; there
  is no `/openapi` endpoint on the console.

**TP-Link Deco mesh behind UniFi**: Decos in AP mode bridge everything,
so each unit shows as a wired client on the port its cable (or its
wired parent) uses; a satellite on wireless backhaul appears behind the
main Deco's port. Ethernet backhaul is auto-detected over the wire and
falls back to wireless when the wire passes no traffic — a marginal
cable produces "wired → wireless → wired → dead" flapping, and every
satellite meshed off that unit drops with it. Swap cables/ports before
swapping Decos.

## 7. Port forwards and dynamic DNS

- Port forwards: `GET rest/portforward` (or `stat/portforward` for the
  effective list); create with `POST rest/portforward` and a body like
  `{"name":"Plex","enabled":true,"pfwd_interface":"wan","src":"any","dst_port":"32400","fwd":"192.168.7.229","fwd_port":"32400","proto":"tcp_udp","log":false}`;
  toggle with `PUT rest/portforward/<_id>` on the full object *(that
  create body verified 2026-09-12 with `proto":"tcp"`; `tcp_udp` for
  both)*. Test from
  **outside** the LAN (a phone on mobile data, or a cloud host): hairpin
  NAT from inside proves nothing. Every forward is an internet-exposed
  service; Tailscale usually makes SSH forwards unnecessary.
- Dynamic DNS: Settings → Internet → WAN → Dynamic DNS, backed by inadyn.
  Providers include DuckDNS, No-IP, Cloudflare, afraid.org, Namecheap,
  EasyDNS and a custom `dyndns`-style URL. Classic object
  `rest/dynamicdns` *(create verified 2026-09-12)*:
  `POST rest/dynamicdns {"service":"duckdns","host_name":"oriolj.duckdns.org","login":"nouser","x_password":"<token>","interface":"wan"}`
  — `_id`, `server: null` come back; edit with a full-object `PUT
  rest/dynamicdns/<_id>`. `stat/dynamicdns` stayed `[]` for minutes
  after creation, so **the gateway's own update is not observable from
  the API**; validate the credential and fix the record immediately
  with the provider's update URL instead (DuckDNS:
  `https://www.duckdns.org/update?domains=<sub>&token=<token>&ip=` →
  `OK`; resolvers cache the old answer for the 60 s TTL). The gateway
  then only has to work on the *next* WAN change. After a router swap
  the ISP usually issues a new lease, so check `dig +short <ddns-name>
  @1.1.1.1` against `curl -s ifconfig.me` the same day *(2026-09-12:
  both old DDNS names were stale after the swap)*.
- **Migrating DDNS credentials from OPNsense**: its legacy `<dyndnses>`
  block stores the DuckDNS **token in `username`** and leaves `password`
  empty; No-IP uses real `username`/`password`. Read the fields by name
  (a positional parse put the hostname into the password slot and
  created a `.duckdns.org` entry with no subdomain — fixed with a PUT).
- UPnP: keep it off (Settings → Internet → UPnP) unless something
  demonstrably needs it.
- **Hairpin (NAT loopback) on the UCG-Fiber — TCP yes, UDP no** *(measured
  2026-09-13, Network 10.6)*: from a LAN client, `<public-ip>:2322/tcp`
  reached the forwarded host, while a UDP probe to `<public-ip>:60500`
  inside a forwarded `60000-61000/udp` range never arrived (the same probe
  to the LAN IP did). Ubiquiti's own port-forwarding article calls
  loopback to the public IP unreliable. Consequence: anything UDP that
  clients use from *inside* the house (mosh, WireGuard, game servers)
  needs a LAN path or split DNS, not the public name. Port ranges are
  written `"60000-61000"` in both `dst_port` and `fwd_port`.
- **mosh through a gateway**: forward `60000-61000/udp` alongside the ssh
  port — mosh-server binds the **first free port from 60001 up**, so a
  narrow range fills with abandoned sessions (a connected `mosh-server`
  never times out; 40 stale ones were found on the minisforum). Invoke
  as `mosh --ssh='ssh -p <port> -o HostKeyAlias=<name>' <real-hostname>`
  — mosh appends the host to the `--ssh` command and must resolve it for
  the UDP leg, so ssh-config aliases with `HostName` break it; use `-o`
  flags instead. Testing mosh non-interactively needs a pty with a size:
  `script -qec "stty rows 24 cols 80; mosh … -- cmd" /dev/null`
  (otherwise `tcgetattr` / a zero-height framebuffer assertion, both
  artefacts). The estate's `m` fish function is the reference: LAN name →
  public forward → tailnet, one `HostKeyAlias` for all three.

## 8. What a UniFi gateway cannot do (plan around it)

- **No Tailscale.** UniFi OS has no native Tailscale; the community
  installer for the UDM is a hack that dies on updates. Put the subnet
  router / exit node on a LAN host (nuc8i7 on the estate) and remove the
  old router's node from the tailnet.
- **No recursive DNS, no Unbound-style host overrides for `.local`.**
- **WireGuard peers cannot be imported.** The VPN Server generates fresh
  server keys and client configs; every peer is re-issued.
- **No config import from another vendor.** A migration is a mapping
  exercise: inventory the old config first (hq's runbook does it from
  OPNsense's `config.xml`), then apply setting by setting.
- **No SSH by default** for the agent; enable it per console only if a
  task truly needs it, and record it.

## 9. References and prior art (checked 2026-09-12)

None of these clears the estate's ">1k stars before installing" bar, so
the skill uses curl/httpx directly; they were read for structure and
endpoint knowledge:

- [sirkirby/unifi-mcp](https://github.com/sirkirby/unifi-mcp) — 809
  stars; MCP servers for Network/Protect/Access with 194 Network tools
  (fixed IP, DNS records, port forwards, DDNS, backups) and a
  preview-then-confirm write model. Best model of the safety UX.
- [hyperb1iss/unifly](https://github.com/hyperb1iss/unifly) — 254 stars;
  CLI + TUI "for humans and agents": DHCP reservations, DNS records,
  firewall, JSON output, raw `api` passthrough, API-key or login auth.
- [t3chnaztea/unifi-skills](https://github.com/t3chnaztea/unifi-skills)
  — 39 stars; five agent skills whose doctrine (read before write,
  full-object PUT, zones default to block, partial port PUTs reset other
  ports, controllers echo unapplied config) this skill adopts.
- [trtmn/agent-skills unifi-api](https://github.com/trtmn/agent-skills/blob/main/unifi-api/SKILL.md)
  — the endpoint catalogue (classic vs Integration, client fields
  `use_fixedip` / `fixed_ip` / `local_dns_record`, report endpoints).
- [dlewis7444/unifi-claude-skill](https://github.com/dlewis7444/unifi-claude-skill)
  — UDM Pro skill; source of the Network 10.x removed-endpoint list and
  the "updates require the full object" rule.
- [colindickson/unifi](https://github.com/colindickson/unifi) —
  Integration-API CLI + skill; the "every mutation requires `--yes`
  after stating the impact" protocol.
- [Art of WiFi: local admin vs API key vs Site Manager](https://artofwifi.net/blog/unifi-api-authentication-local-admin-vs-api-key-vs-site-manager)
  and [uchkunr/unifi-best-practices](https://github.com/uchkunr/unifi-best-practices)
  — auth modes and version requirements.
- [DNSControl UniFi provider](https://docs.dnscontrol.org/provider/unifi)
  — the `static-dns` v2 endpoint, record types, delete-then-create.
- Ubiquiti help: [DNS records and local hostnames](https://help.ui.com/hc/en-us/articles/15179064940439-UniFi-DNS-Records-and-Local-Hostnames),
  [Gateway dynamic DNS](https://help.ui.com/hc/en-us/articles/9203184738583-UniFi-Gateway-Dynamic-DNS).

## 10. Checklist — a UniFi console taking over a LAN

- [ ] Old router fully backed up and inventoried (config export in the
      encrypted store; reservations, forwards, DDNS, VPN, DNS listed).
- [ ] Wizard done with the ISP VLAN/PPPoE facts from that inventory;
      firmware current; local admin in the password manager.
- [ ] Same gateway IP and subnet as before; DHCP range, lease, domain
      set explicitly (not the `.6`–`.254` default).
- [ ] Reservations applied from a plan file, MACs checked against the
      NIC actually in use; drifted devices power-cycled.
- [ ] Local DNS records for the names other systems use; `dig` forward
      and reverse tested; NetAlertX-style PTR consumers re-checked.
- [ ] Only the port forwards that still matter, tested from outside.
- [ ] One DDNS account, verified against the new public IP.
- [ ] UPnP off; ad-blocking decided; `.unf` backup downloaded to secrets.
- [ ] API key in the secrets store, catalogued; old router's node removed
      from the tailnet; docs and changelog updated.
