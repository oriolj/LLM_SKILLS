---
name: tailscale
description: Operate Tailscale across the estate — node sharing semantics (one device, one user, quarantined, subnet routes NOT included), MagicDNS naming and the shared-node FQDN tell, HTTPS/TLS certs (the `tailscale cert` diagnostic, the Certificate Transparency price, why a published name is still unreachable) and `tailscale serve` vs `funnel`. Use when sharing a host with another account or tailnet, putting a service behind a real cert or a clean URL, debugging "why can't this machine reach that one", auditing what a share actually exposes, or when the user mentions tailnet, MagicDNS, ts.net, node sharing, tailscale serve/funnel/cert, or an exit node.
---

# Tailscale — sharing, naming and TLS

Estate context: several tailnets, one per scope, and they share nodes with
each other rather than dual-joining boxes. Facts below are verified on the
live estate with the date noted; re-verify anything undated.

| Scope | Tailnet | Notes |
|---|---|---|
| Personal (oriolj) | `ainu-universe.ts.net` | HTTPS certs **enabled** 2026-09-09 |
| EnaCast / Enantena | `armadillo-tawny.ts.net` | |
| SmartupSoft | — | its boxes live on the EnaCast tailnet |

`tail4d837.ts.net` is **dead** — an old SmartupSoft identity. Any doc still
naming it is stale.

## 0. Direct vs relayed (DERP) — diagnose before touching any router

Tailscale relays through DERP only when UDP NAT traversal fails; a
relayed peer feels like 40–100 ms extra and throttled throughput. Three
commands answer "why is this relayed" without guessing
*(method verified 2026-09-12 from minisforum behind the UCG-Fiber)*:

```sh
tailscale netcheck            # this side's NAT: UDP, MappingVariesByDestIP, PortMapping, nearest DERP
tailscale ping --c=5 --timeout=5s <peer>   # "pong … via <ip>:41641" = direct; "direct connection not established" = DERP
tailscale status --json | jq -r '.Peer[] | select(.Online) | "\(.HostName)\t\(.CurAddr // "-")\t\(.Relay)"'
```

Reading it:

- **`MappingVariesByDestIP: false`** = easy NAT (endpoint-independent
  mapping). Direct connections work to any peer that is not itself
  behind a hard NAT; **no port forward and no UPnP/NAT-PMP is needed on
  this side**. The UCG-Fiber with UPnP off measures as easy NAT.
  `MappingVariesByDestIP: true` = hard (symmetric) NAT: forward UDP
  `41641` to the one host that matters most (or give each LAN host its
  own `tailscaled --port` and forward each), or enable NAT-PMP so
  tailscaled can map a port itself.
- **`PortMapping:` empty** just means no UPnP/NAT-PMP/PCP was offered —
  irrelevant on easy NAT.
- Idle peers show only their DERP home (`mad`, `nue`, `fra`) and no
  `CurAddr`; that is not "relayed", it is "no path negotiated yet".
  Judge by `tailscale ping` after a few packets, or by `CurAddr` while
  traffic flows.
- **A public-IP server that stays on DERP is the server's fault**, not
  the home router's: its host firewall drops inbound UDP `41641`
  (Tailscale can still hole-punch out, but a fully blocked port plus a
  cloud firewall in front leaves only the relay). The estate's
  `shared/ansible` baseline `firewall.yml` opens `41641/udp` in ufw for
  exactly this reason — a server that is relayed has not had the
  baseline applied, or has a provider-side firewall in front.
  2026-09-12 sample from home: `infra-monitoring` direct via
  `159.69.48.55:41641`, while `monitor-1-nc`, `storage-1` and
  `whalehet-01` stayed on DERP `nue`.
- LAN peers (nuc8i7, the Mac mini) go direct over the LAN address
  (`via 192.168.7.x:41641`, 3 ms). If a LAN peer is relayed, look at the
  peer's own firewall or Wi-Fi client isolation on the AP.

What NOT to do: open UPnP on the router "to help Tailscale" (it does not
need it on easy NAT and it exposes every UPnP-capable device), or
forward `41641` to a laptop that roams.

## 1. Node sharing — what it does and does not grant

Sharing is per **device** and per **user**. Both halves matter and people
get the second one wrong.

- *"Sharing gives the recipient access to only the shared machine in your
  tailnet, and nothing else."*
- *"A shared machine is visible only to the individual recipient user — it
  is not visible to the recipient user's entire tailnet."*

So the recipient's colleagues, their admin and their other tailnet members
see nothing; a second person needs a second invite. The recipient also gets
nothing else of yours.

**Quarantine, and it only runs one way.** Shared machines *"can respond to
incoming connections from the tailnet they're shared to, but cannot start
connections on their own."* The recipient dials in; your box cannot dial
out into their network.

**Subnet routes are NOT included** — the trap most likely to waste an hour:
*"Shared machines do not advertise subnets to the tailnets they're shared
into."* Sharing the subnet router gets them the router, **not** the LAN
behind it. Giving someone access to a `192.168.x.0/24` needs an **external
user invitation** to your tailnet instead, which is a far broader grant.
Decide deliberately; don't reach for it because a share "didn't work".

Other mechanics: exit-node use is an opt-in checkbox at share time; a
machine cannot be shared with a tag; the recipient must be Owner/Admin/IT
admin of a tailnet (automatic on a personal plan); revoke via admin console
→ Machines → the machine's Share menu → Revoke invite.

### A share grants the WHOLE node, every port

There is no per-service share. Anything the box listens on is reachable by
the recipient unless a **Tailscale ACL** scopes it. Audit this before
sharing a box that runs more than the one service you have in mind.

Live example (nuc8i7, 2026-09-09): the box was shared into another tailnet
while running an unauthenticated NetAlertX UI whose `query_json.php` serves
the SMTP password, Pushover tokens and API token in cleartext. Its doc
said "do not expose beyond the LAN" — the share had silently made that
false months earlier. Per-user scope was the only thing containing it.

**When you share a node, re-read what else that node serves.** A doc's
"LAN only" assumption expires the moment a share exists.

## 2. Reading `tailscale status` — the shared-node tell

A peer shown by its **full FQDN** is a node shared in from another tailnet;
a peer shown by **short hostname** is native to this tailnet.

```
100.101.158.96  nuc8i7                                    oriolj@  # native
100.65.141.20   internal-1-coolify.armadillo-tawny.ts.net oriol@   # shared in
```

This is the cheapest way to answer "is X already shared into Y?" — run
`tailscale status` on any box in Y and look for X's full name. It beats
asking, and it caught two stale hq claims on 2026-09-09 (a share documented
as pending had existed for a while; another pointed at a dead node).

**A machine can answer on different addresses on each side.** nuc8i7
reports `100.101.158.96` for itself yet answers on `100.101.158.94` from
the tailnet it is shared into — same `direct 192.168.7.229:41641`
endpoint, one box, cause not established (2026-09-09). Consequence:
**never write a `100.x` literal in a doc, config or link.** Use the
MagicDNS name, which is correct from every side. (This is also the standing
global rule; here is a concrete reason it exists.)

## 3. MagicDNS

- Suffix: `tailscale status --json` → `MagicDNSSuffix`, or `tailscale dns
  status`. `DNSName` on the self record gives the full FQDN.
- A shared node **keeps its origin name** on the receiving tailnet
  (`internal-1-coolify.armadillo-tawny.ts.net` stays that everywhere), so
  URLs written against it survive being shared. Nothing in a consuming
  app's config has to change.
- MagicDNS must be on before HTTPS certs can be enabled.

## 4. HTTPS certificates

### Diagnosing availability — use `tailscale cert`, nothing else

```
tailscale cert --cert-file /tmp/c.pem --key-file /tmp/k.pem <fqdn>
```

Disabled, it says so outright:

```
500 Internal Server Error: your Tailscale account does not support getting TLS certs
```

The alternatives are silent about the cause and will cost you time:
`CertDomains: null` in `status --json` is the same condition with no
explanation, and **`tailscale serve --https=443` simply hangs** instead of
erroring (observed 2026-09-09, v1.102.3).

### Enabling

Admin console → **DNS** → **HTTPS Certificates** → **Enable HTTPS**, then
acknowledge the public-ledger notice. It is **tailnet-wide**, not per host.
There is **no API credential for Tailscale anywhere in the estate**, and
the toggle is not known to be API-driven — so this is always the user's
click. Put it in `USER_TODO.md`, don't try to automate it.

### The price: Certificate Transparency

Certs come from Let's Encrypt, and every publicly-trusted cert is written
to **Certificate Transparency logs** — append-only, publicly searchable,
permanent. Browsers have required CT since 2018, so this is not a Tailscale
choice and there is no way to opt out while having a trusted cert.

What that does and does not mean:

- **Published:** the FQDN of every host you actually issue a cert for, plus
  the tailnet name. Hosts you never issue a cert for stay unlisted.
- **Not published:** anything else, and it cannot be withdrawn later.
  Turning HTTPS back off stops future issuance; it does not unlog.
- **A published name is not a reachable one.** Verified 2026-09-09 against
  Google, Cloudflare and Quad9: a `*.ts.net` MagicDNS name returns
  `NOERROR` with **no address** from public resolvers. A CT-log reader gets
  a string, not a destination. Behind it is CGNAT (`100.64.0.0/10`),
  unroutable across the internet, and reaching it still requires a
  WireGuard key the tailnet issued.
- Net: the exposure is **reconnaissance only**. Fine for `nuc8i7`;
  genuinely bad for `client-northwind-prod`. That asymmetry is exactly why
  Tailscale ships it off by default and makes you acknowledge it — and why
  tailnets get random names like `ainu-universe` rather than your org's.

**Say this plainly when asked to enable it.** The decision is whether the
hostnames are sensitive, not whether to click.

### What HTTPS actually buys inside a tailnet

Not wire encryption — WireGuard already provides that, and tailnet HTTP was
never plaintext on the wire. It buys **browser behaviour**: no warnings,
and the page becomes a **secure context**, which unlocks APIs browsers
refuse over plain HTTP (service workers, clipboard, notifications,
camera/mic, WebAuthn). Plenty of self-hosted apps half-break without it.
Plus the URL loses its port.

Costs beyond CT: a 90-day renewal cycle that becomes a background
dependency, Let's Encrypt issuance rate limits, and Funnel becoming
possible (below).

## 5. `serve` vs `funnel`

```
tailscale serve --bg 3000          # https://<fqdn>/ -> localhost:3000, TAILNET ONLY
tailscale serve status             # human view
tailscale serve status --json      # the authoritative view
tailscale serve --https=443 off    # remove
```

`serve` is tailnet-only and prints "(tailnet only)". `funnel` publishes to
the **public internet** — different command, separately opt-in per service,
and it needs the `funnel` node attribute in ACLs.

**Confirm scope from `serve status --json`:** an absent `AllowFunnel` key
means tailnet-only. Don't infer it from the human output.

```json
{"TCP":{"443":{"HTTPS":true}},
 "Web":{"nuc8i7.ainu-universe.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:3000"}}}}}
```

Enabling HTTPS removes Funnel's safety catch — before certs exist, `funnel`
cannot work at all; afterwards it is one command away. Worth saying out
loud when you enable certs, even though nothing is exposed by doing so.

Config lives in tailscaled's state, so `serve` survives reboots. tailscaled
renews the cert on the 90-day cycle while serve runs.

### Wiring an app behind it

The proxy sends the **bare FQDN** as `Host` (no port). Anything validating
host headers needs that value listed *in addition to* the `:port` form, or
it breaks the moment you move to 443. Do both at once — see the
gethomepage case in hq `docs/homepages.md`, where `HOMEPAGE_ALLOWED_HOSTS`
missing the bare FQDN is a page-wide outage, not a degraded mode.

`serve` proxies to `localhost:<port>`, so the app still has to listen on
the host. Putting it behind `serve` does **not** close the original port —
LAN and `:port` tailnet access stay open until you change the bind.

## 6. Gotchas worth keeping

- **A node freshly re-logged into a tailnet can be reachable one way only**
  (bikecrm-prod-2, 2026-09-12): the node pinged the hub fine while the hub's
  netmap showed it with no relay and no path (`tailscale status --json`:
  `Relay ""`, `CurAddr ""`, stale `LastHandshake`) — every inbound connection
  timed out for ~20 min. `systemctl restart tailscaled` on the re-logged node
  re-registered it instantly. Diagnose with `tailscale ping` from BOTH ends
  before blaming firewalls; and anything that had cached a dead connection
  (an Alloy agent's WAL push) needs its own restart afterwards.
- **Containers cannot use MagicDNS on a systemd-resolved-stub host** (Ubuntu
  22.04, Tailscale's DNS on the tailscale0 link only): Docker hands containers
  the resolved UPSTREAM resolvers, so `monitor-1-nc` resolves on the host and
  fails inside every container. Use the literal tailnet IP in container
  config on such hosts (the estate's documented exception) — Debian 13 hosts
  do not have this problem.
- **Key expiry silently kills a node.** Disable key expiry on every server
  node in the admin console (also in `fleet-observability`).
- **A LAN-only box may still not be on the tailnet.** Check before assuming
  a hostname resolves — several home boxes are LAN-only and absent from
  `tailscale status`.
- **`tailscale status` on the wrong machine misleads.** A workstation is
  logged into ONE tailnet at a time (`tailscale switch --list` shows which,
  and it is per-machine). Ask the box in question, not your laptop.
- **`ip route get <100.x>`** tells you whether an address routes via
  `tailscale0` or leaks to the LAN gateway — quick answer to "why does this
  IP not work from here".
- **`--accept-routes` on, LAN still unreachable → nobody is advertising
  it.** Don't debug the client; list the routes the tailnet actually
  offers: `tailscale status --json` → each peer's `PrimaryRoutes` /
  `AllowedIPs`. Only `/32`s plus `0.0.0.0/0` on the exit nodes means no
  subnet router exists on *this* tailnet — and a subnet router on another
  tailnet does not count, even when its node is shared in (§1). Verified
  2026-09-12: no node on the EnaCast tailnet advertises the home LAN
  `192.168.7.0/24`; the only candidate (`OPNsenseKiras`) is on the personal
  tailnet, and nuc8i7 arrives as a share. Workarounds from a laptop: use
  a home box as exit node (`tailscale set --exit-node=<home-box>
  --exit-node-allow-lan-access`), or make a home box that is native to
  the laptop's tailnet advertise the route (`tailscale up
  --advertise-routes=192.168.7.0/24` + approve in the admin console).
