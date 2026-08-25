---
name: fleet-observability
description: Integrate any app or server with the estate's monitoring (Prometheus + Loki + Grafana on monitor-1-nc) — per-host Alloy agents, the oj.* docker-label contract, authenticated log shipping, app /metrics endpoints, and per-project `make logs`. Use when onboarding a server to monitoring, adding logs/metrics to a project, asked "how do I see prod logs from my machine", "add this app to grafana", "tag services for loki", "ship logs to loki", "expose django/go metrics", deploying the Alloy agent, or reviewing a compose file's oj.* labels. Works on Coolify AND non-Coolify hosts, docker and dockerless (native mode). Covers the label cardinality rules, the socket-proxy requirement, the loki-gateway auth split (write vs read creds), django-prometheus multiprocess traps, and the rollout checklist with the first-hour timestamp-reject expectation.
---

# Fleet observability — integrating apps and servers with the monitoring stack

The hub is **monitor-1-nc** (`hq-monitoring` repo, deployed by Coolify):
Prometheus (metrics, pull), Loki (logs, push, compose-internal), Grafana
(dashboards + email alerts). This skill is the *integration* side: how a
server or an application joins it. Design doc: hq
`shared/docs/monitoring.md`. Coolify mechanics: `coolify-deploy` skill.

Everything rides the **tailnet** — joining Tailscale is a hard prerequisite
for any host before its agent (Prometheus scrapes agents over it; agents push
logs over it; nothing observability-related touches a public interface).

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

## 3. The per-host agent (ansible-managed compose)

Deployed by `shared/ansible` (role `observability_agent`), NOT as a Coolify
resource: monitoring must keep watching hosts when Coolify is broken, and
per-host config (hostname, creds, network name) comes from the inventory.
Role drops `/opt/observability/{docker-compose.yml,config.alloy,nginx.conf}`
and runs `docker compose up -d`. Agent updates = bump the pinned image in
the role, run the play.

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
  `Config.Env` — so **no credential may live in container env** on any
  monitored host (file-based secrets; see `coolify-deploy` §9). The agent
  makes container env READABLE to anything that reaches the proxy.

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
    url = "http://<hub-tailnet-ip>:3100/loki/api/v1/push"
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
- **Celery**: don't hand-roll — run the maintained standalone
  `celery-exporter` as one more compose service pointed at the broker,
  labeled with `oj.metrics.port`. Task counts/latency/queue depth per task
  name; pairs with the `celery-deploy-safety` skill.
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

## 6. `make logs` — prod/beta logs from the dev machine

Workstations are on the tailnet; `logcli` + the `reader` cred give real
tailing. homelab/ansible deploys `~/.config/oj-loki/env`:

```bash
LOKI_ADDR=http://<hub-tailnet-ip>:3100
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
