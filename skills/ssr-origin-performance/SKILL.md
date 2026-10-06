---
name: ssr-origin-performance
description: Find where the CPU of a Node SSR origin goes (Astro / Next / any Node server behind a CDN, on a VPS) and decide what to change — host-health check before profiling, CPU per request from the container cgroup against the CDN's origin-reaching counts, profiling a node:cluster worker over the inspector (CDP) without hanging, GC threads the profile does not show, a local benchmark that replays the production URL mix and records the backend API, which Node flags and runtime swaps are worth testing, and the static-vs-SSR caching lessons (what makes an SSR site behave like a static one). Use when an SSR origin or a Node server runs hot, "high CPU on the VPS", "where is the load coming from", "is it the code or the box", "should we upgrade Node / switch to Bun / rewrite in Rust", "benchmark before deploying", or when planning ISR-like caching for SSR pages. Static marketing sites: static-site-performance; browser metrics: core-web-vitals; Cloudflare mechanics: cloudflare-deploy; metrics/logs wiring: fleet-observability.
---

# SSR origin performance (Node behind a CDN)

Learned on the EnaCast public site (Astro 7 SSR, `@astrojs/node` in a 6-worker `node:cluster`,
Coolify on an OVH VPS behind Cloudflare), 2026-10-06. Reference record and numbers:
`enacast-astro` branch `coolify`, `docs/origin-performance.md`; benchmark: `scripts/bench/`.

## 0. Check the box before the code (10 seconds)

**The first measurement on a hot VPS is a microbench against a known-good host of the same
model**, not a profile. Three single-thread Node scripts in `node:<ver>-slim`: an ALU loop, a
memcpy (`Float64Array.set` of 256 MiB × 8), an SSR-shaped allocate + JSON + string-concat loop.

- A **memcpy / allocation deficit with normal ALU speed is the host** (memory over-committed or
  a noisy neighbour on the hypervisor). EnaCast 2026-10-06: vps-2 memcpy 0.08–0.13 GB/s vs 6.1–6.7
  GB/s on its identical twin; ALU within 1.3–2.3×; SSR-shaped workload 6–16 s vs 0.39 s. Steal read
  0–1 %, no swap, same page faults: nothing inside the guest showed it.
- SSR is allocation- and memory-bound, so every render pays a memory deficit. **No code change or
  Node flag can be judged on such a box**; fix or move the host first.
- Not separated by the microbench alone: a sick host vs your own workers saturating memory. Re-run it
  at the traffic trough, or pause the app for 10 s (a production action — ask).
- Every probe on a saturated production box costs it CPU. Ask the question, then stop.

## 1. CPU per request in production

- **Numerator:** the container cgroup, `cpu.stat usage_usec` (`/sys/fs/cgroup/system.slice/docker-<id>.scope/`).
  Timestamp both reads (`date +%s.%N`); never infer the window from what ran in between (a
  `docker run` on a saturated box took ~20 s to start and made a 5 s test look like "13 cores").
- **Denominator:** what reached the origin, from the CDN. Cloudflare GraphQL
  `httpRequestsAdaptiveGroups` with `cacheStatus_notin: ["hit","stale","updating"]`, every zone
  (SaaS zone + clients' own zones), dims `clientRequestHTTPHost`, `clientRequestPath`,
  `edgeResponseStatus`, `userAgent`, plus `avg { originResponseDurationMs }`. Split by class
  (pages, assets, redirects, API routes, 404s): an asset is ~free, a page is not.
- Prove nothing bypasses the CDN: `ss` on the proxy's netns (all peers = the tunnel daemon).
- **Even static files slow at the origin = event-loop starvation**: time one hashed asset straight
  from the container (`curl` its IP:port). 17–195 ms for a file that takes 1 ms means renders hold
  the loop; per-render cost is the problem, not the queue.

## 2. Profiling a worker (inspector over CDP)

- Find the busy process first: `/proc/<pid>/stat` utime+stime deltas per worker over 30 s. A cluster
  primary or an idle worker yields a 100 % idle profile. Short samples mislead about balance: check
  the cumulative totals before claiming "3 of 6 workers do the work".
- `kill -USR1 <pid>` opens the inspector on `127.0.0.1:9229` inside the container (one at a time:
  "address already in use" otherwise). SIGUSR1 to tini (PID 1) is forwarded to the primary.
- A ~40-line CDP client (Node 22 has `WebSocket` global): `json/list` → `Profiler.enable`,
  `setSamplingInterval` 500 µs, `start`, wait, `stop`; aggregate self time per function and per module,
  inclusive time per component chunk (walk parents in `profile.nodes`).
- **Close with `Runtime.evaluate process._debugEnd()` WITHOUT awaiting it** (the reply never comes:
  the script hangs with "unsettled top-level await"), print first, `process.exit` after ~500 ms.
- ESM workers: no `require` in `Runtime.evaluate`; use `process.getBuiltinModule('v8')` for
  `getHeapStatistics()` / `getHeapSpaceStatistics()` (old vs new space tells a leak from churn).
- **The JS profile does not sample V8's GC helper threads.** A "75 % idle" main thread with busy GC
  threads (`/proc/<pid>/task/*/stat`) means allocation churn; the profile under-reports it.

## 3. A local benchmark that predicts production

Reference: `enacast-astro` `scripts/bench/` (README there). The parts that matter:
- **The production artefact:** build the deployed commit's Dockerfile (`git archive <sha> | docker build -`),
  same env names, same worker count, a CPU set and memory limit.
- **The production URL mix:** sample unique `(host, path)` pairs from the CDN's origin-reaching
  requests, proportional to class share. A small warm set of home/list URLs (the old load test)
  measures the wrong regime: crawlers walk the long tail with cold app caches.
- **The backend recorded once, replayed after:** a tiny record/replay proxy (first GET forwarded and
  stored, then served from disk; `STRICT` never reaches production; optional latency so renders
  stay in flight as long as in production). Run it as a container on the bench network: the host
  firewall can drop bridge→host traffic (`UND_ERR_CONNECT_TIMEOUT`).
- **One variant = fresh container (cold app cache) + cold pass + warm pass**, one JSON line each
  (CPU ms/request from the cgroup, cores busy, p50/p95, KB/response, RSS).
- Compare ratios between variants on one machine; change one thing per variant; re-run the baseline.
- Results that held (EnaCast, Node 22 → 24, `--max-semi-space-size=64`, Sentry DSN on, API latency,
  16 vs 40 connections): all within noise. Runtime knobs rarely beat "render less".

## 4. What to change, in order

1. **Fewer renders reaching the origin** (CDN and bots): Tiered Cache (per-POP misses of hashed
   assets were 25 % of origin requests), robots.txt then edge rules for training crawlers and SEO
   tools (keep search/user agents and your own monitors), negative caching of 404s.
2. **Runtime config** only with a benchmark row: worker count vs vCPUs left for GC/JIT and the proxy.
3. **Cheaper renders:** no jsdom per request (sanitise at write time), validate once at cache fill,
   cache parsed objects instead of re-parsing JSON per hit, smaller API payloads, sample tracing.
4. **A runtime swap (Bun) only past a pass bar** (≥ 25–30 % less CPU per render, no p95 regression,
   identical HTML for every URL, instrumentation proven to still run).
5. **A rewrite in a compiled language** only if CPU per render still dominates after all of that.
   Static generators (Zola, Hugo) do not apply to a multi-tenant SSR app.

## 5. Static vs SSR: making SSR pages behave like static ones

- A static site's cost is fixed at build; an SSR page's is paid per CDN miss. The CDN is the static
  layer: long `s-maxage` + async `stale-while-revalidate` + **purge by tag on every content change**.
- **A deploy must not empty the cache.** Purge-everything-on-deploy exists only because cached HTML
  references hashed assets the new build lacks. Keep previous builds' assets served (union of
  `_astro/` across builds, or a shared asset origin) and drop the deploy purge; then the islands' API
  routes must stay backward compatible for the TTL window.
- Raise TTLs gradually (hours first, a ceiling like 48 h), each step after a per-scope purge check
  (save → page updated) and with an emergency full purge kept. A missed purge becomes a TTL-long
  staleness bug: correctness beats hit rate.
- Clock-dependent HTML (relative dates, now playing, banner windows) cannot sit behind a long TTL:
  short caps per route, or move it into an island.
- An origin HTML cache must be **shared** (Valkey/Redis keyed by host + path + normalised query,
  with the page's tags), never per-process: per-worker caches multiply memory, divide hit rate, and
  purges reach one worker only.
- **An overloaded origin must not answer 404 for upstream failures** (search engines drop the page): answer 503 +
  `Retry-After`, no-store, and let the CDN serve stale (`stale-if-error`). Mechanics: the `seo` skill, "Edge / middleware
  pitfalls" item 6 (EnaCast, 2026-10-06: homes 404'd to Googlebot while the origin was saturated).
- Telemetry before tuning: hit/miss of every layer (CDN analytics, `redis_exporter`), origin renders
  per hour, CPU per request. Without them a cache change cannot be judged.
