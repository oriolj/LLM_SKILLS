---
name: unifi
description: Operate a UniFi gateway (Cloud Gateway Fiber/Max/Ultra, Dream Machine, UniFi OS consoles) from the CLI/API without the usual traps — the three API layers behind the UniFi OS proxy (Integration v1, classic `api/s/<site>`, v2) and which one carries what, X-API-KEY auth vs local-admin login, DHCP reservations (fixed IP + local DNS record on the client object), DHCP range/lease/domain on the network object, static DNS records, port forwards, dynamic DNS, backups, the setup-wizard API (ISP VLAN tag, the "302 until setup completes" gotcha), full-object PUT and read-before-write doctrine, and what a UniFi gateway cannot do (Tailscale, recursive DNS). Use when configuring or auditing the home UCG-Fiber (192.168.7.1), migrating a router to UniFi, restoring DHCP leases/reservations, adding a port forward or DDNS, when `dig` against the gateway returns no local names or PTRs, when a UniFi API call returns 401/404, or when the user mentions UniFi, Ubiquiti, UCG, UDM, Dream Machine, UniFi OS, fixed IP, DHCP reservation, or the Network application.
---

# UniFi gateways — API layers, reservations, and the traps

Estate context: one UniFi console, the **UniFi Cloud Gateway Fiber** that
replaced OPNsense as the home router on 2026-09-12 (homelab scope,
`https://192.168.7.1`, Oriol's personal UI account). Everything specific
to that migration — the OPNsense inventory, the cutover checks, the
reservation plan — lives in hq:
`homelab/docs/network/ucg-fiber-migration.md`, `lan-address-book.md`,
`ucg-fiber-reservations.csv`, and the applier
`homelab/tools/unifi-fixed-ips.py`. This skill holds the mechanics that
outlive that migration. Facts marked *(verified YYYY-MM-DD)* were seen on
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
  *(verified 2026-09-12)*.
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
