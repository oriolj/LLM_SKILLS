---
name: cdmon-dns
description: Use the CDmon Domains API safely — DNS records on the zones hosted at CDmon (enacast.com). Use BEFORE any nameserver change (CDmon signs zones by default — moving NS without disabling DNSSEC first takes the domain dark with SERVFAIL everywhere), when creating/editing/deleting DNS records for enacast.com or any CDmon-hosted zone, when the user mentions CDmon, when wiring a CNAME for a Pages/Vercel/Coolify deployment on enacast.com, or when planning wildcard/delegation records for EnaChat branded chats. Covers the API base URL and auth, the DNS endpoints, and the SAFETY RULES — this key operates on a PRODUCTION zone with ~150 records serving every radio client, and some endpoints charge real money.
---

# CDmon Domains API (DNS)

## ⚠️ FIRST: which zone lives where (as of 2026-08-26)

CDmon is the **registrar** for both domains, but only one has its **DNS**
here. Editing the wrong one is a silent no-op — the record exists and nothing
resolves from it.

| Domain | Registrar | Authoritative DNS | Edit with |
|---|---|---|---|
| `enacast.com` | CDmon | **CDmon** (ns1-3.cdmon.net) | this API |
| `enacast.chat` | CDmon | **Cloudflare** (zone `78798ebd9e4d55ea03c5ac24e3d4537d`) | the Cloudflare API — see `cloudflare-deploy` |
| `santjust.chat` | CDmon | **CDmon** | this API — one apex `A @ → 141.95.29.64` (EnaChat client custom domain, live 2026-08-25; apex cannot be a CNAME) |

`enacast.chat` was registered 2026-08-26 and is the product's main domain; its
nameservers point at Cloudflare so the apex can serve Cloudflare Pages and so
Traefik can get DNS-01 wildcard certs for tenant chat hosts. **Do not recreate
`enacast.chat` records here** — the only CDmon-side operation it needs is the
nameserver change, which is human-only (see the safety rules).

## 🔥 Before ANY nameserver change: check DNSSEC first

**CDmon signs zones by default.** Moving nameservers without removing the DS
record takes the domain **completely dark** — the registry still publishes a DS
for the old provider's key, the new nameservers can't produce matching
signatures, and every validating resolver answers **SERVFAIL**. Not a partial
outage: no A record, no MX, nothing, for everyone.

Burned on `enacast.chat`, 2026-08-26: NS moved to Cloudflare, then both Google
and Cloudflare public resolvers returned SERVFAIL while Cloudflare's edge
answered plain HTTP with a bare `409`. The tell is SERVFAIL from a *validating*
resolver while the delegation itself looks correct.

```bash
# 1. ALWAYS check before touching /dns
curl -sL https://rdap.org/domain/<domain> | python3 -c \
  "import json,sys; print(json.load(sys.stdin).get('secureDNS'))"
#    delegationSigned: true  ->  disable DNSSEC FIRST, then move nameservers

# 2. Disable (removes the DS from the registry)
curl -s -X POST "$API/dnssec" -H "apikey: $KEY" -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"data": {"domain": "<domain>", "action": "disable"}}'

# 3. Verify the DS is gone (delegationSigned: false, dsData: []) before /dns
```

Recovery if you already flipped: disable DNSSEC as above — the registry drops
the DS within seconds, then resolvers clear their cached failures as the DS TTL
expires (~1h; they recover at different times, so partial resolution is normal
mid-recovery). To re-sign later, take the DS from the *new* provider (Cloudflare
publishes one per zone) and add it at the registrar — never leave the old one.

Order that always works: **disable DNSSEC → change NS → re-enable with the new
provider's DS.**

## Two limits that decide architecture

- **Record types are A, CNAME and TXT only — no ALIAS/ANAME.** A CDmon-hosted
  zone therefore **cannot point its apex at Cloudflare Pages**: a CNAME at the
  apex is illegal DNS and Pages publishes no stable IP. If the requirement is
  "the bare domain serves the static site", the zone must move to a provider
  that flattens (Cloudflare), or the site must move to something with a fixed
  IP. Subdomains are fine here — that is how `chat.enacast.com` works.
- **No lego/Traefik DNS-01 provider exists for CDmon**, so wildcard
  certificates are impossible while a zone lives here. That is the actual
  reason EnaChat's tier-1 branded chats (`<town>.xat.…`) were never activated
  on enacast.com, and why the new domain went to Cloudflare instead.

Field notes from 2026-08-25 (first use: creating `chat.enacast.com` for the
EnaChat comercial site on Cloudflare Pages). Official docs (Apiary, the raw
blueprint is fetchable): https://domainsapi1.docs.apiary.io/ —
`GET /api-description-document` on that host returns the full API blueprint
as markdown when the rendered page won't load (it 502s intermittently —
curl with `--retry 3 --retry-delay 2`).

## ⚠️ SAFETY RULES (Oriol: "be extra careful on cdmon api")

The key operates on the LIVE `enacast.com` zone: ~150 records, including
every radio client's website CNAME, streaming hosts, Google MX for the
company mail, and DKIM/SPF records. There is no staging, no dry-run, no
undo, and no record history.

- **Read-only by default.** `getDnsRecords` freely; any WRITE beyond adding
  a brand-new record needs explicit confirmation from Oriol first.
- **NEVER call the money endpoints**: `register`/`create` (domain
  registration), `renew`, `transfer`, `restore` charge the account balance.
  Nothing an agent does should ever need them.
- **Never touch** `dns` (nameserver changes), `dnssec`, `block`,
  `whoisprivate`, `contacts/modify`, `autorenewal/manage` — account-level
  operations, human-only **by default**. One scoped exception exists: on
  2026-08-26 Oriol explicitly said "change cdmon yourself" for the
  `enacast.chat` nameserver move (and the DNSSEC disable it turned out to
  need). That authorization was for that domain, which was one day old and
  resolving nothing. It does **not** generalise: on `enacast.com` these calls
  can take every radio client's site and the company mail down at once, so
  they still need a fresh, explicit yes each time.
- **Adding a NEW record (unique host+type) is the safe operation** — it
  cannot clobber anything. Still: `getDnsRecords` FIRST to confirm the
  host doesn't exist, and again AFTER to verify exactly one record changed.
- **Edit/delete match on `host`+`type` only** — with multiple records on
  the same host+type (MX, NS, TXT sets), an edit/delete may hit more than
  you intend. For those, list first, show Oriol the exact record(s), and
  get a yes.
- The API returns `{"status": "ok"|"ko", "data": …}` — always check
  `status`, a 200 does not mean success. Under concurrent writers it also
  answers `{"message":"API rate limit exceeded"}` with NO `status` key —
  treat a missing `status` as "not done", re-list, retry.
- **Several agents writing the zone at once is fine, but the proof is a
  SET diff, not a count.** Diff records by `(host, type, value, ttl)`
  before/after and assert "my record present, nothing removed"; the count
  moved 160 → 169 in minutes on 2026-08-28 from seven parallel writers.
  Never assume the host you want is still free: `getDnsRecords`
  immediately before the write.

## Auth + base URL

- Base: `https://api-domains.cdmon.services/api-domains/<endpoint>`
- Every call is **POST** with JSON, even reads.
- Headers: `apikey: <key>` + `Accept: application/json` +
  `Content-Type: application/json`.
- Key: `hq/homelab/secrets/cdmon.env` → `CDMON_API_KEY` (age-encrypted
  committed copy; grep/cut to read, never `source`). Regenerating the key
  in the CDmon panel invalidates the old one.

## Domain list (read-only) — and the SECOND CDmon account

```bash
curl -s -X POST "$API/domains/list" -H "apikey: $KEY" \
  -H "Accept: application/json" -H "Content-Type: application/json" -d '{"data": {}}'
# -> {"status":"ok","data":{"msg":"Domain list for client enantena","result":[{"domain":…},…]}}
```
61 domains in the **enantena** account on 2026-08-28 (`docs/domains.md` in
hq has the full owner/registrar/DNS table). **A second CDmon account
exists** that this key cannot see: `oriolj.com` (personal — registrar
CDmon but live DNS on **Route 53**), plus the CDmon-hosted zones
`humans2agents.com`, `rutakas.com`, `fichachat.com`, `smartupsoft.com`,
`xescomerce.com`, `construcat.cat`. Its key (when issued) is
`hq/homelab/secrets/cdmon-oriolj.env` → `CDMON_ORIOLJ_API_KEY`. **Oriol's
rule (2026-08-28): no domain work for personal products until that key
exists** — never reach for the enantena key for a personal zone.

## DNS endpoints (types supported: A, CNAME, TXT)

```bash
KEY=$(grep '^CDMON_API_KEY=' $SECRETS/cdmon.env | cut -d= -f2)
API=https://api-domains.cdmon.services/api-domains

# List (do this before AND after any write)
curl -s -X POST "$API/getDnsRecords" -H "apikey: $KEY" \
  -H "Accept: application/json" -H "Content-Type: application/json" \
  -d '{"data": {"domain": "enacast.com"}}'

# Create (host is the LABEL, not the FQDN; destination for A/CNAME, value for TXT)
curl -s -X POST "$API/dnsrecords/create" -H "apikey: $KEY" \
  -H "Accept: application/json" -H "Content-Type: application/json" \
  -d '{"data": {"domain": "enacast.com", "type": "CNAME", "ttl": 900,
       "host": "chat", "destination": "enachat-website.pages.dev"}}'

# Edit — current selects by host+type; new carries ttl + destination/value
# {"data": {"domain": "…", "current": {"host": "x", "type": "CNAME"},
#           "new": {"ttl": 900, "destination": "y"}}}      → /dnsrecords/edit
# Delete — {"data": {"domain": "…", "type": "CNAME", "host": "x"}} → /dnsrecords/delete
```

- **Field asymmetry, verified**: records READ back with `value`
  (`{"type","host","ttl","value","priority"?}` inside `data.result`), but
  are WRITTEN with `destination` (A/CNAME) or `value` (TXT). Don't echo a
  listed record back into create/edit without renaming the field.
- Success shapes: list → `{"status":"ok","data":{"msg":…,"result":[…]}}`;
  create → `{"status":"ok","data":"Record added successfully"}`.
- TTL convention in the zone: **900** for almost everything.
- `host: "@"` = apex. Wildcards work as labels (`*.ai` exists as an A
  record). Sub-zone NS delegation works too (`test` is delegated to AWS).
- Propagation is fast: a created record answered from `ns1.cdmon.net`
  within seconds.

## The enacast.com zone — what lives there (2026-08-25 snapshot)

- Radio-client websites: dozens of `<radio>` CNAMEs → Vercel
  (`*.vercel-dns-016.com`); apex + `www` → 91.134.113.207.
- `chatapp` → coolify-ovh-vps-1.enacast.com (EnaChat app — old host, kept
  indefinitely: installed embeds hardcode it);
  `chat` → enachat-website.pages.dev (old comercial URL; Pages 301s it to
  `enacast.chat`, the main domain since 2026-08-26 — keep the record).
- Company mail: Google MX on `@` + Mailgun/SES/Resend TXT+DKIM — mail
  breaks if these are touched.
- Planned (see enachat/plans/custom-domains.md): wildcards
  `*.xat` / `*.chat` for branded per-town chats — as CDmon records they
  can be plain wildcard CNAMEs to the app host; remember the explicit
  `chat` record and a `*.chat` wildcard coexist as separate records.
