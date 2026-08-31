---
name: fleet-observability
description: Integrate any app or server with the estate's monitoring (Prometheus + Loki + Grafana on monitor-1-nc) — per-host Alloy agents, the oj.* docker-label contract, authenticated log shipping, app /metrics endpoints, and per-project `make logs`. Use when onboarding a server to monitoring, adding logs/metrics to a project, asked "how do I see prod logs from my machine", "add this app to grafana", "tag services for loki", "ship logs to loki", "expose django/go metrics", deploying the Alloy agent, or reviewing a compose file's oj.* labels. Works on Coolify AND non-Coolify hosts, docker and dockerless (native mode). Covers the label cardinality rules, the socket-proxy requirement, the loki-gateway auth split (write vs read creds), django-prometheus multiprocess traps, and the rollout checklist with the first-hour timestamp-reject expectation.
---

# Fleet observability — integrating apps and servers with the monitoring stack

The hub is **monitor-1-nc** (`hq-monitoring` repo, deployed by Coolify):
Prometheus (metrics, pull), Loki (logs, push, compose-internal), Grafana
(dashboards + email alerts). Error tracking is separate: **GlitchTip**
(Sentry-compatible, on the `infra-monitoring` host) — see §5b. This skill is the *integration* side: how a
server or an application joins it. Design doc: hq
`shared/docs/monitoring.md`. Coolify mechanics: `coolify-deploy` skill.

Everything rides the **tailnet** — joining Tailscale is a hard prerequisite
for any host before its agent (Prometheus scrapes agents over it; agents push
logs over it; nothing observability-related touches a public interface).

**Addressing rule (Oriol's standing preference): use Tailscale MagicDNS
short hostnames, never raw `100.x` IPs, in every URL** — homepage links,
`LOKI_ADDR`, scrape target lists, DSNs, docs (`http://monitor-1-nc:3000`,
`http://infra-monitoring:8000`). Names survive IP changes and read like the
inventory. The one place an IP is still required is a **compose port bind**
(`${TAILNET_IP}:3000:3000` — bind addresses must be literal IPs).


> **Scope boundary — host monitoring is Beszel, not this stack** (Oriol,
> 2026-08-29). Host up/down, CPU/RAM/disk/network and container stats
> for every server in every scope come from the one Beszel hub
> (`hq/shared/docs/beszel.md`, agents via the `shared/ansible`
> `beszel_agent` role). This skill covers logs (Loki) and application
> metrics (Prometheus/Grafana) on monitor-1-nc. Don't add a second
> host-metrics pipeline, and don't reach for Checkmate/Uptime Kuma —
> Checkmate was retired 2026-08-29, Uptime Kuma is being folded into
> Beszel.

## Loki 429s that are NOT rate limits — the active-stream ceiling

`429` with body `maximum active stream limit exceeded when trying to create
stream {...}` is **`limits_config.max_global_streams_per_user`** (default
5000), not ingestion rate. Symptom pattern: existing hosts keep writing
fine while EVERY stream from a newly enrolled host is rejected — looks
like broken auth/agent, is neither (auth failures are 401 from the
gateway). Fix: raise the limit in `loki-config.yaml` (hq-monitoring; 20000
since 2026-08-30) — and mind the cause: on Coolify hosts the `container`
label carries per-deploy name suffixes, so every redeploy mints new
streams and the ceiling fills with very few hosts. Prefer stable labels
(`coolify_app`, `service`) over raw container names. Alloy retries 429s
with backoff (`loki_write_request_duration_seconds_count{status_code=...}`
on :12345 tells the truth); after fixing the limit, restart Alloy to
re-ship promptly instead of waiting out the backoff.

## 1. Architecture (one agent, both signals)

```
per host:  alloy ──(pull /metrics)── central Prometheus   (tailnet)
           alloy ──(push logs, basic auth)── loki-gateway → Loki
```

- **One Alloy replaces node_exporter + promtail.** `prometheus.exporter.unix`
  embeds the node_exporter collectors (cpu, mem, swap, disk, filesystem,
  hwmon); `loki.source.journal` + `loki.source.docker` ship logs. One agent,
  one config, one thing to roll out.
- **Metrics are pulled** (central Prometheus scrapes each host's Alloy on
  `:12345`): keeps `up{}` semantics, so target-down alerting works without
  absent() gymnastics. **Logs are pushed** (Alloy → gateway).
- **Temps are bare-metal only** — KVM/VPS guests expose no hwmon sensors;
  don't chase empty `node_hwmon_*` on cloud instances.
- Hosts fall in three shapes, all supported by the same ansible role:
  1. **Coolify docker host** — compose agent, joins the `coolify` network
     (external) so it can scrape app containers by IP.
  2. **Non-Coolify docker host** — same compose agent; the external network
     name is a role var (or omitted).
  3. **Dockerless host** (streaming boxes, appliances) — native Alloy
     package: journald + unix exporter only, no docker pipeline. Do NOT
     install Docker just to run a monitoring agent.

## 2. The label contract — `oj.*` docker labels

Every service in every project compose declares:

```yaml
labels:
  oj.project: enacast        # the product/repo, NOT the container
  oj.env: prod               # prod | beta | dev — nothing else
  oj.service: web            # optional; defaults to the compose service name
  # only on services exposing app metrics:
  oj.metrics.port: "8000"
  oj.metrics.path: "/metrics"   # optional; default /metrics
```

Alloy relabels these into `project`, `env`, `service` on BOTH logs and
metrics, plus `host` and `job`. The same selector then works everywhere:
`{project="enacast", env="prod"}` in Loki ≡ `{project="enacast", env="prod"}`
in Prometheus — which is what makes Grafana's graph↔logs jumps line up.

**Cardinality rules (Loki grinds to a halt if you break these):**

- Labels are for **bounded, long-lived values** — tens of values max per
  label. `project/env/service/host/job/unit/container` is a full set; Loki's
  own guidance is "the fewer labels the better" (default cap: 15).
- **Never label** per-request/per-entity values: user ids, request ids, trace
  ids, URLs, IPs. Those go IN the log line (query-time filtering is fast) or
  as **structured metadata** (Loki ≥3.x, schema v13 — high-cardinality fields
  indexed-adjacent without exploding streams).
- A new label value = a new stream = new chunks + index entries. A label
  that takes 1000 values multiplies your stream count by 1000.
- Untagged containers fall back to `project=<compose project name>` and are
  surfaced in a Grafana "untagged containers" panel
  (`count by (project) ({oj_tagged="false"})`) — stragglers must be visible,
  not silently absorbed.

**Setting oj.* labels on Coolify resources (verified 2026-08-25, EnaChat):**

- **Applications (Dockerfile buildpack): the `custom_labels` API field
  works.** It is base64 and PRE-FILLED with Coolify's generated Traefik
  labels — `GET /applications/{uuid}`, decode, **append** the `oj.*` lines,
  re-encode, PATCH, redeploy. Never replace the existing content (it IS the
  Traefik routing). Verified: labels land on the container, routing intact.
  Workers have an empty field; just set the oj.* lines.
- **Database resources have no custom_labels**, but need none: Coolify
  stamps `coolify.projectName` (= project if named right),
  `coolify.environmentName` (`production` → relabel to `prod`) and
  `coolify.database.subType` (`standalone-postgresql` / `standalone-redis` →
  relabel to `postgres`/`redis`). The role's alloy config carries these
  fallbacks generically, so `service=postgres|redis` needs no per-host map.
  DB streams still show `oj_tagged="false"` (correct: no oj.* labels).

## 3. The per-host agent (ansible-managed compose)

Deployed by `shared/ansible` (role `observability_agent`), NOT as a Coolify
resource: monitoring must keep watching hosts when Coolify is broken, and
per-host config (hostname, creds, network name) comes from the inventory.
Role drops `/opt/observability/{docker-compose.yml,config.alloy,nginx.conf}`
and runs `docker compose up -d`. Agent updates = bump the pinned image in
the role, run the play.

**Status (2026-08-25): the role EXISTS and the first agent is LIVE** on
coolify-ovh-vps-1 (opt-in `observability` inventory group; monitor-1-nc is
deliberately excluded — the hub compose runs its own Alloy there). Shipped
**logs-only**: journald + docker with the full label relabeling, WAL, tailnet
bind on :12345. Still planned: the metrics pipeline (unix exporter, app
`/metrics` discovery, central Prometheus target) and the rest of the fleet.
Per new host: generate a password, add `agent-<host>:<pw>` to the hub app's
`LOKI_WRITERS` Coolify env + redeploy the hub, add
`LOKI_AGENT_PASSWORD_<HOST>` to `homelab/secrets/loki-agents.env`, put the
host in `observability`, run `--tags observability`.

The agent is a **pair**: `alloy` + `socket-proxy`, because the Docker socket
is host-root and `:ro` does not restrict the API. The proxy is plain nginx
with an **exact-path allowlist** (GET `_ping`, `version`, `containers/json`,
`containers/{id}/json`, `containers/{id}/logs`, `networks`; everything else
403; non-GET 403). Copy it from `hq-monitoring/socket-proxy/nginx.conf` —
it is smoke-tested there. Two non-obvious requirements, both found the hard
way:

- `/networks` must be allowed: `discovery.docker` calls it, and without it
  discovery silently yields **zero targets** while journald keeps flowing.
- Inspect is allowed (Alloy needs TTY framing detection) and returns
  `Config.Env` — so ideally **no credential lives in container env** on any
  monitored host (file-based secrets; see `coolify-deploy` §9). **On Coolify
  hosts that ideal is false**: Coolify injects every UI env var into
  container env, so app secrets ARE readable via inspect. The accepted
  trade-off (first fleet agent, coolify-ovh-vps-1 2026-08-25): keep the
  inspect route (Alloy needs it), keep the proxy **unpublished and only on
  the agent compose's private default network** — the complete set of things
  that can reach it is then the two pinned upstream images (alloy + nginx).
  Never attach the proxy to the coolify network, never publish it, never add
  a third service to the agent compose without re-reading this.

Compose essentials (full template lives in the ansible role):

```yaml
services:
  alloy:
    image: grafana/alloy:<pinned>          # never :latest
    hostname: ${HOSTNAME}                  # else host label = container id → stream churn per redeploy
    pid: host                              # process visibility for unix exporter
    volumes:
      - /:/host/root:ro,rslave             # rootfs for disk/filesystem collectors
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /var/log/journal:/var/log/journal:ro
      - /etc/machine-id:/etc/machine-id:ro
      - ./config.alloy:/etc/alloy/config.alloy:ro
      - alloy-data:/var/lib/alloy/data     # WAL + positions — MUST persist
    ports:
      - "${TAILNET_IP}:12345:12345"        # central Prometheus scrapes here; tailnet bind, never 0.0.0.0
    networks: [default, coolify]           # coolify external — only on Coolify hosts
  socket-proxy:
    image: nginx:<pinned>
    user: "0:0"
    volumes:
      - ./nginx.conf:/etc/nginx/docker-proxy.conf:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
networks:
  coolify: { external: true }              # role templates this out on non-Coolify hosts
```

Alloy config building blocks (per-host `config.alloy`, templated by ansible):

```alloy
// host metrics — the node_exporter replacement
prometheus.exporter.unix "host" {
  rootfs_path = "/host/root"
  procfs_path = "/host/proc"
  sysfs_path  = "/host/sys"
}
// expose everything for the central Prometheus to PULL on :12345
prometheus.scrape "self" { targets = prometheus.exporter.unix.host.targets ... }

// journald + docker logs via the proxy, relabeled from oj.* labels:
//   __meta_docker_container_label_oj_project → project, _oj_env → env,
//   _oj_service (fallback com_docker_compose_service) → service
// app-metrics discovery: containers carrying oj.metrics.port become scrape
// targets on <container-ip>:<port><path> — reachable because the agent sits
// on the same docker network. The metrics port stays UNPUBLISHED.

loki.write "hub" {
  endpoint {
    url = "http://monitor-1-nc:3100/loki/api/v1/push"
    basic_auth { username = "agent-<host>" password_file = "/etc/alloy/loki.pass" }
  }
  wal { enabled = true }   // survive gateway restarts/outages; bounded by max_wal_time
}
```

`loki.write`'s WAL keeps logs through hub restarts and network blips; an
outage longer than its retention truncates oldest-first — acceptable, alert
on the outage itself, don't size the WAL for days.

## 4. The loki-gateway (how push gets authenticated)

Loki has no auth of its own and its query API returns log content, so raw
3100 is **never** published (not even on the tailnet). The hub's compose has
a `loki-gateway` nginx on `${TAILNET_IP}:3100` with **two credential
classes** in one htpasswd:

| Cred | Allowed paths | Held by |
|---|---|---|
| `agent-<host>` (one per host, revocable) | POST `/loki/api/v1/push`, GET `/ready` | the host's Alloy |
| `reader` | GET `/loki/api/v1/{query,query_range,tail,labels,label/*,series}` | workstations (`make logs`, logcli) |

Writers can't read (a compromised host cannot browse other hosts' logs);
readers can't push. Tailnet reachability is the outer layer, auth the inner.
Passwords come from Coolify env vars on the hub; the per-host agent password
lands on each host via ansible (from the controller's decrypted secrets).

## 5. App metrics — how a project exposes internals

The contract: **expose `/metrics` on a port that is NOT published**, then
declare it with labels. Alloy scrapes it over the docker network; nothing
public, so the endpoint needs no auth of its own.

```yaml
  web:
    labels:
      oj.project: enacast
      oj.env: prod
      oj.metrics.port: "8000"     # container port, not a host port
```

Per stack (the estate's languages — Django/Python, Go, Next.js, Astro):

- **Django**: `django-prometheus` (request/DB/cache metrics + `/metrics`).
  ⚠️ Under gunicorn (multi-worker) you MUST use multiprocess mode:
  `PROMETHEUS_MULTIPROC_DIR=/tmp/prom` set in the **start script** (not from
  Python — it must reach child processes), the dir **wiped on container
  start** (`rm -rf "$PROMETHEUS_MULTIPROC_DIR"; mkdir -p …` before
  `exec gunicorn`), and know the consequences: counters reset on every
  deploy (`rate()` handles it), `Gauge` needs an explicit
  `multiprocess_mode`, `Info`/`Enum` don't work, and gunicorn's worker
  recycling (`max-requests`) needs `mark_process_dead(pid)` in a
  `child_exit` hook or dead workers' gauge files linger. The classic
  symptom of missing multiproc: metrics **flicker** between values as each
  request hits a different worker's private registry.
  Field notes from wiring EnaChat live (2026-08-25, `prometheus_client`
  directly — the right call when you need a token-gated view + a business
  collector anyway and pg/redis exporters cover the DB/cache layer):
  - `--max-requests 1000` (house default) makes the `child_exit` hook
    **non-optional**: workers recycle every few minutes of real traffic,
    and each dead pid leaves gauge mmap files behind. A 3-line
    `gunicorn.conf.py` (`child_exit` → `multiprocess.mark_process_dead
    (worker.pid)`) added with `-c` fixes it.
  - **Business metrics = a custom collector computed per scrape**, not
    counters sprinkled through app code: `collect()` yields
    `GaugeMetricFamily` from single GROUP-BY ORM aggregates (~10 cheap
    queries at the 60 s interval). Absolute truths survive deploys, and the
    collector **never touches the mmap files** — it runs in whichever
    worker serves the scrape, sidestepping the multiproc Gauge trap
    entirely. Registration is mode-dependent: multiproc → register on the
    per-scrape registry next to `MultiProcessCollector(registry)`;
    single-process (dev/tests) → default REGISTRY at import.
  - `prometheus_client` APPENDS `_total` to every `CounterMetricFamily`
    name (`llmwatch_celery_tasks` → `llmwatch_celery_tasks_total`) — read
    the live endpoint before writing dashboards/alerts, never the source.
  - Per-tenant labels (town/client slug) are fine exactly when tenants are
    bounded-tens; the app version rides a labeled gauge
    (`app_info{version="<sha>"} 1`) because Info doesn't exist in
    multiproc.
- **Tailnet-only `/metrics` on a Coolify Dockerfile app (the hardened
  variant — EnaCast AI, 2026-08-31, verified end to end).** Add to the
  app's `custom_labels` a dedicated router + allowlist referencing the
  GENERATED service name:
  `traefik.http.routers.metrics-<uuid>.rule=Path(\`/metrics\`)` with
  `priority=1000` (Path rules are short — default length-based priority
  loses to the site's Host rule), `entryPoints=https`, `tls=true`,
  `tls.certresolver=letsencrypt`, `service=https-0-<uuid>`, and a
  middleware `ipallowlist.sourcerange=100.64.0.0/10,172.16.0.0/12,127.0.0.1/32`.
  Three non-obvious facts: (1) **tailscaled MASQUERADEs tailnet traffic it
  forwards into the docker bridge**, so Traefik sees every tailnet client
  as the bridge gateway (172.x) — without the RFC-1918 range the allowlist
  blocks the tailnet too, while real internet clients always keep their
  public source IP (403); (2) the hub then scrapes
  `https://<host-tailnet-ip>:443` with `tls_config.server_name: <domain>`
  (SNI serves the right cert; the router matches by Path, so the IP Host
  header is fine for Traefik) — but **Django needs the tailnet IP in
  ALLOWED_HOSTS** or the scrape 400s DisallowedHost; (3) test all four
  paths after: public+token→403, site→200, tailnet+token→200, tailnet
  bare→401.
- **Coolify Dockerfile apps: the token-gated public-origin scrape path.**
  Publishing the app port as a host port would **disable blue-green**, and
  the Coolify API rejects IP-qualified `ports_mappings` anyway
  (`coolify-deploy` §7c) — so scrape the app's existing public https
  origin with a bearer token: `/metrics` view 401s without
  `Authorization: Bearer $METRICS_TOKEN` and **fails CLOSED when the env
  is unset in prod**; token = runtime-only Coolify env on the app, same
  value on the hub as an environment-sourced compose secret read via
  `authorization.credentials_file: /run/secrets/<name>` (never a token
  inside prometheus.yml). ⚠️ `promtool check config` STATS every
  credentials_file — the validate gate must mount a dummy `/run/secrets`
  or it fails on the missing file.
- **supercronic schedulers (Go/Django cron containers)**: `supercronic
  -prometheus-listen-address 0.0.0.0:9746 <crontab>` exposes
  `supercronic_executions`, `supercronic_successful_executions`,
  `supercronic_currently_running` and
  `supercronic_cron_execution_time_seconds_{bucket,count,sum}` (labels
  `command`, `position`, `schedule`; verified v0.2.34, 2026-08-28). Failures
  = `executions − successful_executions` (there is no separate failed
  counter to alert on). Two birds: that listener is also what Coolify's UI
  health check probes (`GET /metrics` on 9746), so a scheduler resource no
  longer needs the UI check OFF. Publish the port for the hub scrape only
  behind the DOCKER-USER tailnet guard (Licita Radar, `oriolj-nc-1`).
- **Third reference implementation** (enantena scope, 2026-08-30):
  **EnaCast/enacast-ai** — `backend/config/prom.py` + `METRICS.md`; hub
  jobs `enacast-ai-{app,postgres,redis}`, dashboard `enacast-ai`, alert
  group `hq;enacast-ai`. Two traps it added: **uuid4-PK models break
  `Count("id")`** (house rule says uuid PKs — always `Count("pk")` in
  collectors), and a **23 GB table must be counted from
  `pg_class.reltuples`** (raw cursor), never `count(*)`, in a per-scrape
  collector. Shape the collector's counts as SEPARATE small aggregates so
  they ride the model's partial indexes — one combined aggregate seqscans
  and detoasts jsonb per row. Its gunicorn conf is `gunicorn_conf.py`,
  NOT `gunicorn.conf.py` — `--config python:gunicorn.conf` would import
  from the installed gunicorn PACKAGE.
- **Second reference implementation** (personal scope, 2026-08-28):
  `oriolj/public_contract_scanner` — `backend/config/prom.py` + `METRICS.md`
  (catalogue-first: every metric documented in the repo, hub jobs
  `licita-radar-app|scheduler|postgres`, dashboards `licita-radar*.json`,
  alert group `hq;licita-radar`). Copy that shape for the next Django app.
- **Celery**: on a compose host, run the maintained standalone
  `celery-exporter` as one more service pointed at the broker, labeled
  with `oj.metrics.port`. **On Coolify Dockerfile apps (worker/beat are
  separate unpublished resources) the exporter has nowhere to be scraped
  either** — the pattern that works (llm-index-watcher, 2026-08-28): Celery
  signal hooks (`task_prerun/postrun/retry`) write per-task counters,
  duration sums and last-start timestamps to Redis hashes, worker and beat
  each run a heartbeat thread setting a TTL key (`heartbeat_sent` only
  fires with events `-E` on — don't rely on it), and the WEB app's
  `/metrics` reads them back as `CounterMetricFamily`/gauges (+ `LLEN` of
  the queue). One scrape path, one token; counters survive deploys because
  they live in Redis. Reference: `config/prom.py` + `config/celery.py` in
  `oriolj/llm-index-watcher`, documented in its `METRICS.md`.
- **Plain Python** (scripts, daemons): `prometheus_client.start_http_server`
  on the internal port; single-process, so none of the multiproc pain.
- **Go**: `promhttp.Handler()` on the app mux (or a second internal-only
  mux). Instrument the golden signals first: an HTTP middleware
  `HistogramVec` — and keep its labels to `code`/`method`(+coarse `path`
  bucket, never raw URLs); the stdlib-style
  `promhttp.InstrumentHandlerDuration` wrappers enforce exactly that.
  Histogram partitioning is expensive: few histograms, few labels, default
  buckets unless you have a reason.
- **Next.js** (self-hosted node server — ours are): `prom-client` via the
  built-in `instrumentation.ts` hook — `register()` runs once at server
  start; guard with `process.env.NEXT_RUNTIME === "nodejs"`, create the
  Registry there, expose it from a `/metrics` route handler. Collect
  `collectDefaultMetrics()` (event loop lag, heap) + request counters.
  Note: this only exists because we self-host the node server — a
  serverless deploy has nothing stable to scrape.
- **Astro**: split by output mode. **Static builds have no runtime to
  instrument** — observability there is the web server's logs (already
  shipped by the host agent) plus uptime/Web-Vitals tooling, not
  Prometheus. SSR with the node adapter = a normal node server: wrap the
  adapter's middleware with `prom-client` exactly like Next.js.
- **Icecast / third-party**: the corresponding exporter container beside
  it, same labeling.
- Metric naming: Prometheus conventions (`<app>_<thing>_<unit>_total`);
  label cardinality bounded exactly like log labels.
- Wire the deployed release into a metric (`app_info{version="<sha>"} 1`)
  so deploys are visible as Grafana annotations.

## 5a-bis. Alert email — Resend SMTP, and the blocked-port trap

Grafana delivers alerts by email through **Resend SMTP**. Two field-verified
facts (monitor-1-nc, 2026-08-25):

- 🔴 **netcup blocks outbound SMTP ports (25/587) by default** on
  vServers/root servers — anti-spam policy. Symptom: every notification
  fails with `dial tcp <ip>:587: i/o timeout` (~10–15 s each), while the
  config looks perfect. **Fix: `smtp.resend.com:2587`** — Resend listens
  there precisely for blocked-port hosts. No support ticket needed. Check
  the provider's egress policy before debugging credentials.
- Delivery health is a metric, not a feeling: Grafana's own
  `/metrics` exposes `grafana_alerting_notifications_total` and
  `…_failed_total` (per integration). The failed counter ABSENT means zero
  failures; present and equal to total means nothing ever left the box.
  And the stack debugs itself — query `{compose_service="grafana"} |~
  "(?i)smtp|notify"` in Loki for the actual dial error instead of hunting
  for docker logs.

**The hub host runs the SAME per-host agent since 2026-08-31** — alloy +
socket-proxy left the hq-monitoring compose and monitor-1-nc joined the
`observability` group, precisely so hub redeploys stop interrupting log
shipping (the agent WALs through the gateway outage). The `alloy`
Prometheus job scrapes all agents' tailnet :12345; `hq-alloy-not-shipping`
is per-host (`sum by (host)`).

**Hub redeploys page their own "Alloy not shipping" alert** — the hub is
a Compose resource (stop→start), every deploy flattens its own Alloy's
`loki_write_sent_entries_total`, and back-to-back deploys exceed the
rule's `for: 15m`. That is why `hq-alloy-not-shipping` is severity
**warning** (downgraded 2026-08-30 after 4 deploys in 25 min paged
priority-1) — batch hub pushes, and don't re-promote it to critical.

**Pushover for paging** (email is an inbox nobody stares at): two contact
points routed by the `severity` label — warning → priority 0, critical →
priority 1 with a distinct sound (bypasses quiet hours; priority 2/emergency
re-alerts until acked and additionally needs `retry`/`expire`). Token + user
key ride the `/run/secrets` pattern via Grafana's `$__file{...}` provisioning
interpolation — **verified working** alongside `$__env{...}` (2026-08-25).
Give critical a much shorter `repeat_interval` (30 m here) than the default
(24 h) — critical should NAG until someone acts.

**Provisioned alert rules do NOT die with their file.** Deleting a
provisioning yml only stops UPDATES — the rules live on in grafana.db,
still firing (a leftover always-true test rule paged every 30 m for an
hour). The only provisioned deletion path is a **`deleteRules:` tombstone**
(uid + orgId) in a file that stays. Two Coolify interactions stack on top:
the repo copy is additive (the deleted yml survives on the server and
re-creates the rules every restart — `rm` it there), and the copy lands
after startup while Grafana reads alerting provisioning ONLY at startup, so
any new provisioning file needs one extra restart to take effect. Verify
with the unauthenticated `/metrics`: `grafana_alerting_rule_group_rules`
lists every live group.

**Alert provisioning files DID load on a plain Coolify redeploy** (2026-08-28,
`licita-radar.yml`: `grafana_alerting_rule_group_rules{rule_group="hq;licita-radar"} 7`
right after the deploy, no extra restart) — the "one extra restart" note
below is the failure mode to check for, not a certainty. Verify with the
`/metrics` counter every time; `grafana_stat_totals_dashboard` counts the
file-provisioned dashboards the same way when the HTTP API login is not
available.

**hq-monitoring's `make validate` creates a dummy for EVERY
`credentials_file` referenced in prometheus.yml** (grep-driven since
2026-08-28) — adding a token-gated job needs no Makefile edit, only the
compose `secrets:` entry + the `smoke.sh` canary export.

**Dashboard iteration needs NO deploys.** The dashboard file provider
WATCHES its directory (`updateIntervalSeconds`), unlike alerting/datasource
provisioning (startup-only). On a Coolify-deployed hub, iterate by scp'ing
the JSON straight into the preserve-repository dir
(`/data/coolify/applications/<uuid>/grafana/dashboards/`) — live within
~30 s — and commit the identical file to git: the next deploy overwrites the
dir from git, so uncommitted server-side edits self-heal away (a feature,
not a bug). Deploys remain the correct transport for scrape-config and
alert-provisioning changes; batch those. Never create dashboards via the
Grafana HTTP API — they land only in grafana.db, which is exactly the
dashboards-lost-with-the-database failure this git-provisioned design
prevents.

**Post-deploy notification timing**: a redeploy restarts Grafana and resets
every rule's `for` clock, so notifications lag by pending-time + group_wait
after each deploy. Diagnose with `grafana_alerting_notifications_total` /
`…_failed_total` (the `/metrics` endpoint answers unauthenticated): zero
failed + zero attempted = timing, not routing — wait before debugging.

To force a real end-to-end email without waiting for repeat_interval
(the nflog dedupes re-notifications for 24 h): create a temporary
always-firing rule (`vector(1)`, `for: 10s`, own ruleGroup so it forms a
fresh alert group) via the provisioning API with `X-Disable-Provenance`,
watch the counters, then DELETE it. A fresh group notifies immediately.

## 5b. Error tracking — GlitchTip (the estate's Sentry alternative)

Errors/exceptions go to **GlitchTip**, not Sentry — it is Sentry-API
compatible, so every project uses the **official Sentry SDKs** pointed at a
GlitchTip DSN. It runs on the `infra-monitoring` host (tailnet MagicDNS
`http://infra-monitoring:8000`), separate from the metrics/logs hub. Logs
tell you *what happened on a host*; GlitchTip tells you *this exception,
grouped, with a stack trace* — a project wants both.

Per stack (all standard Sentry SDK setup, only the DSN differs):

- **Django/Python**: `sentry_sdk.init(dsn=…, environment=…, release=…)` with
  the Django (+Celery) integrations. `send_default_pii=False` unless decided
  otherwise; keep `traces_sample_rate` at 0 or very low — GlitchTip is for
  errors, perf tracing eats its Postgres.
- **Go**: `sentry-go`, `sentry.Init` + recover middleware.
- **Next.js/Astro (node)**: `@sentry/nextjs` / `@sentry/node`.

Non-negotiables, wired to the rest of the estate's rules:

- `environment` must equal the compose's **`oj.env`** value (prod|beta|dev)
  so errors and logs/metrics slice the same way.
- `release` = the deployed **git SHA** (the global release-identifier rule;
  on Coolify use `SOURCE_COMMIT`) — enables regression detection.
- The DSN is a credential: **Coolify env var, runtime-only** (or the
  project's secrets mechanism) — never committed.

**Ask the user — do not invent these:**

1. **The DSN itself.** Projects are created by hand in the GlitchTip UI
   (per project × env, or one project with environments — the user's
   choice); an agent cannot self-serve one. Ask for it, or ask the user to
   create the GlitchTip project and paste the DSN.
2. **Reachability of the DSN host from the app's servers.** The GlitchTip
   UI is tailnet-only today; whether app servers send events over the
   tailnet or a public ingest endpoint exists is deployment-specific —
   confirm before wiring an SDK that would silently fail to deliver
   events (SDKs swallow transport errors by design).

- DOCKER-USER tailnet-only guard hosts as of 2026-08-30: coolify-ovh-vps-1, oriolj-nc-1, enacast-ai-fsn1-1 (script + oneshot unit per `coolify-deploy` §7c).

## 6. `make logs` — prod/beta logs from the dev machine

Workstations are on the tailnet; `logcli` + the `reader` cred give real
tailing. homelab/ansible installs logcli (note: Arch's `extra/logcli`
lags the hub — pin the release binary matching the hub's Loki minor into
`~/.local/bin` when it matters). `~/.config/oj-loki/env` is **not yet
ansible-deployed** (tracked in homelab/docs/TODO_AND_EXPLORE.md); today it
exists hand-made on one workstation:

```bash
LOKI_ADDR=http://monitor-1-nc:3100
LOKI_USERNAME=reader
LOKI_PASSWORD=…
```

Project Makefile pattern (project name hardcoded per repo):

```make
PROJECT := enacast
logs:            ## tail prod logs
	@set -a; . ~/.config/oj-loki/env; set +a; \
	logcli query --tail --follow '{project="$(PROJECT)", env="prod"}'
logs-beta:
	@set -a; . ~/.config/oj-loki/env; set +a; \
	logcli query --tail --follow '{project="$(PROJECT)", env="beta"}'
logs-grep:       ## make logs-grep Q="traceback"
	@set -a; . ~/.config/oj-loki/env; set +a; \
	logcli query --since 1h '{project="$(PROJECT)", env="prod"} |~ "(?i)$(Q)"'
```

LogQL crib: `|= "text"` exact, `|~ "regex"`, `| json | status >= 500`,
`| service="celeryworker"` to narrow inside the project stream set.

## 7. Rollout checklist (per host, in order)

1. Host on the tailnet (`tailscale status`), enrolled in shared/ansible.
2. `oj.*` labels added to the project composes on that host FIRST — else
   everything arrives as fallback-tagged and needs relabeling later.
3. Agent play (`--tags observability`); on Coolify hosts confirm the
   `coolify` external network name matches.
4. Central Prometheus target added (generated from the ansible inventory —
   a host in the inventory IS a host in monitoring).
5. Verify in order: `up{host="X"} == 1` → host dashboard has data →
   `{host="X"}` returns journald lines → docker logs per project →
   app-metrics targets up.
6. **Expect a noisy first hour**: Alloy reads each container's whole log
   history and Loki 400-rejects everything older than
   `reject_old_samples_max_age` (7 d) as "timestamp too old". That is the
   guard working — watch that drops fall to zero, don't page on the burst.
   (A host whose containers were all recreated recently shows NO burst —
   coolify-ovh-vps-1's first rollout was silent because every container was
   hours old. Absence of the burst is not a mis-wire.)
7. One host at a time; watch ingest rate, stream count
   (`loki_ingester_memory_streams`), and hub disk before the next.

## 8. What NOT to do

- **One agent per HOST — never an Alloy/promtail/vector sidecar per compose
  stack.** Sidecars duplicate memory, connections and config, and every
  stack update becomes a monitoring update. The host agent's
  `discovery.docker` sees new stacks the moment they start; deploys need no
  monitoring change at all. Apps log to **stdout/stderr, JSON if cheap**,
  never to files inside the container.
- Don't switch the metrics path to `prometheus.remote_write` push without a
  reason: pull keeps `up{}` semantics (target-down alerting for free) and
  needs no `--web.enable-remote-write-receiver` on the hub. Push is for
  hosts that genuinely cannot accept an inbound scrape.
- No `docker logs`-based cron scrapers, no `ssh host docker logs` runbooks —
  that's what `make logs` replaces.
- Don't publish `/metrics` on a host port "temporarily" — published ports
  bypass ufw (see `coolify-deploy`).
- Don't add a label because it might be useful; add it when a real query
  needs it. Removing a high-cardinality label later means dead streams
  forever in the index.
- Don't point two Alloys at the same journald/docker source (e.g. old
  promtail left behind) — duplicate streams with half-matching labels.
