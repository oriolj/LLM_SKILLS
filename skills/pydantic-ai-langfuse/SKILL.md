---
name: pydantic-ai-langfuse
description: Implement LLM features in Python with PydanticAI + Langfuse observability. Use when adding LLM calls to any Python/Django project, integrating PydanticAI agents, wiring Langfuse tracing, testing agents without hitting real models, choosing model strings, debugging "Unknown provider" / instrument errors, fetching websites as LLM input, or controlling LLM costs in batch pipelines. Also use for LLM cost attribution questions — "who is spending", cost per client/tenant/user, "n/a is my top user", missing or wrong cost in Langfuse, trace user_id/session_id/tags not showing up, auditing which code path emits untagged traces. Also when Langfuse mails "ingestion suspended" / usage limit exceeded, when asked which project used the Langfuse quota, when a project has BOTH Langfuse and OpenTelemetry tracing (Tempo) and its database/Redis/HTTP spans show up in Langfuse, or before adding OTel instrumentation to a project that already uses Langfuse. Covers PydanticAI 2.x API changes, OTel→Langfuse setup, TestModel/FunctionModel testing, Django-specific OOM traps, SPA scraping, and rate-limit-safe batch scoring.
---

# PydanticAI + Langfuse: Python LLM implementation

House rules: **always PydanticAI** for LLM calls, **always Langfuse** for tracing (graceful no-op when keys are unset). Never call provider SDKs directly.

## PydanticAI essentials

```python
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent

class MatchScore(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str = Field(max_length=300, description="Una frase en español")

def build_scoring_agent() -> Agent:          # builder fn, NOT module-level instance
    return Agent(settings.LLM_MODEL, output_type=MatchScore, system_prompt=PROMPT)

result = build_scoring_agent().run_sync(prompt).output   # validated MatchScore
```

- **Model strings** are `provider:model` from env (e.g. `LLM_MODEL=google:gemini-3.8-flash`, `anthropic:claude-haiku-4-5`). API keys via env: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.
- **Build agents in a function, not at import time.** Import-time `Agent(...)` couples module import to provider config, breaks in keyless environments (CI), and makes test override painful. A `build_*_agent()` function is trivially monkeypatched in tests.
- **Build prompts in a separate pure function** (`build_scoring_prompt(profile, item) -> str`) so prompt content is unit-testable with zero LLM calls.
- **Validators as guardrails**: normalize LLM output in `@field_validator` (dedupe, regex-check codes, strip junk) instead of trusting the model or post-processing at call sites.
- Deps extras matter: `pydantic-ai-slim[google,anthropic]` — the `google` extra brings `google-genai`.
- **`output_type` is not a convenience, it is the JSON guarantee.** Measured
  on Panotxa (raw `google-genai`, `response_mime_type="application/json"`,
  NO `response_schema`, `gemini-3.5-flash-lite`, 2026-09): **3.6 % of
  responses were not valid JSON** — a stray `-` before a key, an unescaped
  `"` inside a string — and a 300-line homegrown repair module rescued 1 in
  11 while being able to silently save a mangled result. JSON *mode* asks
  for JSON; only a schema (`output_type` here, `response_schema` on the raw
  SDK) *constrains* the decoder. If you inherit a module that parses LLM
  JSON by hand, the fix is the schema, not a better repair heuristic —
  write-up: NutriLens `backend/docs/GEMINI_JSON_FAILURES.md`.

## PydanticAI 2.x breaking changes (hit in the wild)

| Old (≤1.x) | 2.x | Symptom if wrong |
|---|---|---|
| `google-gla:gemini-…` | `google:gemini-…` | `ValueError: Unknown provider: google-gla` |
| `Agent(..., instrument=True)` | `Agent.instrument_all()` (global, call once at startup) | `TypeError: unexpected keyword argument 'instrument'` |

When touching an unfamiliar pydantic-ai version, introspect before writing code:
`python -c "import inspect, pydantic_ai; print(pydantic_ai.__version__); print(inspect.signature(pydantic_ai.Agent.__init__))"`

- **`AgentRunResult.usage` is a PROPERTY in 2.x** (`RunUsage`), not a
  method. `result.usage()` raises `TypeError: 'RunUsage' object is not
  callable` — and if that line sits AFTER the provider call, the tokens are
  paid and the row never gets saved (LLM Index Watcher, 2026-09-02: every
  successful run died there; tests passed because their fake result used a
  lambda). Write `usage = result.usage() if callable(result.usage) else
  result.usage`, and put the post-answer bookkeeping inside a try that
  records the failure — one unexpected exception inside a Celery chord
  header means the chord callback (scoring) never runs. Token fields are
  `input_tokens` / `output_tokens` (old `request_tokens` names are gone).
- **Gemini web-search grounding gives you no source URLs through
  pydantic-ai 2.8**: the `NativeToolReturnPart.content` for `web_search` is
  `{"search_suggestions": "<style>…google.com chips…"}` — Google's HTML
  widget, not `grounding_chunks`. A generic "walk every part for URLs"
  citation harvester finds only google.com links (skip-listed). Treat
  Google citations as unavailable until the grounding metadata is surfaced
  (or call the Gemini API directly for it).
- **`genai_prices.calc_price` raises `LookupError` for a model it does not
  know yet** (`gemini-3.8-flash` on 0.0.71) — brand-new defaults price as
  `None` silently. Keep a settings alias map (unknown id → priced sibling)
  and log the miss once per process.

## Langfuse tracing (OTel exporter pattern)

One init function, called once at process start (Django: end of `settings.py` — covers gunicorn, manage.py commands, and cron jobs alike). **No-op without keys** so dev/test never need Langfuse. **Not in a project that also traces to Tempo**: there the tracing provider is installed first and `init_langfuse` must not set a provider of its own, or the tracing one is refused (section "Langfuse is for LLM calls only", point 5):

```python
# config/observability.py
import base64, os
_initialized = False

def init_langfuse():
    global _initialized
    if _initialized: return
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
    base = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    if not (pk and sk): return
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=f"{base.rstrip('/')}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {auth}"})))
    trace.set_tracer_provider(provider)
    from pydantic_ai import Agent
    Agent.instrument_all()          # model calls, tokens, cost per trace
    _initialized = True
```

Deps: `langfuse>=3.11`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`.

Two layers, both required:
1. `Agent.instrument_all()` → model-call detail (tokens, cost, tool calls).
2. `@observe` on entry functions → function-level input/output. Without it traces show "agent run" with `input=null`.

```python
from langfuse import observe

@observe(name="profile_agent")                      # str args: capture is fine
def generate_profile_draft(website_text: str, ...): ...

@observe(name="match_scoring", capture_input=False)  # Django models: NEVER capture
def score_match(profile, tender): ...
```

### Langfuse traps

- **NEVER pass Django ORM objects through a capturing `@observe`.** The serializer recurses into model `_state`/related managers and allocates GBs → worker OOM (SIGKILL) before the function body runs. Use `capture_input=False, capture_output=False` and attach sanitized data inside via `start_as_current_generation(input=...)` / `generation.update(output=...)`.
- **`langfuse.openai.OpenAI` wrapper buffers streamed responses** to write the trace — defeats client-side byte caps. Use the native client + explicit `start_as_current_generation` spans when you need streaming size limits.
- Without keys, `@observe` logs a one-time "client will be disabled" warning and continues — harmless, don't chase it.
- **Inherited code defaults to capturing everything.** A codebase merged in on 2026-08-29 had `@observe(name=...)` on functions taking image bytes and citizen questions, plus `start_as_current_observation(..., input=prompt)` — the full RAG prompt (question + archive text) went to Langfuse. Rule: every `@observe` carries `capture_input=False, capture_output=False`; generation spans record `model`, `usage_details`, `cost_details` only. Guard it with a static test that regex-scans the codebase for `@observe(` without both flags and for `input=`/`output=` inside `start_as_current_observation(` (`apps/clients/tests/test_langfuse_privacy.py` in enaarchive is the template).

## Langfuse is for LLM calls only (quota, and the global-TracerProvider leak)

**Rule (Oriol, 2026-10-10): Langfuse receives LLM calls and nothing else.**
Request, database, Redis, HTTP and task spans go to Tempo
(`fleet-observability` skill). Langfuse bills **events = traces +
observations + scores**, added up over every project of the *organization*;
the free tier is 50,000 per billing period and when it is exceeded ingestion
is suspended until the reset date (the mail says which) or an upgrade.

What a suspension does and does not do (Panotxa, 2026-10-10): the ingestion
endpoints answer 403, so the SDK logs `Failed to export span batch code:
403 … Ingestion suspended` at ERROR on every flush (dozens an hour in Loki
and the error tracker). **Prompt management and the read API keep working**,
so an app that fetches its prompts from Langfuse is not down, and the usage
can still be audited. To wait for the reset without the error noise, set the
SDK's own `LANGFUSE_TRACING_ENABLED=false` on every process and redeploy: no
spans are created, `@observe`d functions and `get_prompt` keep working
(verified on 3.8.1). Record the revert date where the owner will see it; a
forgotten flag is a project with no LLM traces.

**The leak.** The Langfuse SDK attaches its span processor to the GLOBAL
OpenTelemetry `TracerProvider`. In a project that also traces to Tempo, that
provider carries every Django/psycopg/Redis/httpx/Celery span, and **Langfuse
v3 (`langfuse<4`) exports all of them** unless its client was built with
`blocked_instrumentation_scopes=[…]`. Panotxa sent 251,023 events in 14 days,
98 % of them database and Redis spans: a real LLM trace was 1 generation
wrapped in ~33 infrastructure spans, and every periodic Celery task was a
trace of its own.

**The trap: a block list on your own client does not apply.** The SDK keeps
one client per public key (`LangfuseResourceManager`) and the first
constructor wins. `@observe` and `langfuse.get_client()` build a default
`Langfuse()` from the `LANGFUSE_*` env vars, with no block list, when no
client exists yet; a later `Langfuse(..., blocked_instrumentation_scopes=[…])`
silently returns that unfiltered one. Panotxa had the block list in its
service module for five weeks and it never applied, because a decorated
function always ran first.

**The fix: filter in the provider you own, not in the client.** Every
Langfuse client, the default one included, reaches the global provider
through one call, `tracer_provider.add_span_processor(<LangfuseSpanProcessor>)`.
So the project's `TracerProvider` is a small subclass whose
`add_span_processor` wraps any processor that comes from the `langfuse`
package in a `SpanProcessor` that forwards `on_end` only for an allow-list of
scopes (`("langfuse-sdk",)`, plus a GenAI instrumentation's scope when one is
adopted) and delegates `on_start` / `force_flush` / `shutdown`. Reference:
NutriLens `backend/config/tracing.py` (`_provider_class`,
`LANGFUSE_ALLOWED_SCOPES`). What that buys:

1. **No dependence on creation order or process type.** A first attempt
   created the filtered client at process start (`AppConfig.ready()` and
   Celery `worker_process_init`). It needed an argv check to skip the Celery
   worker's main process (the client's score and media threads do not survive
   the fork, and `flush()` joins their queues), read the SDK's private
   `_instances` to check itself, and still leaked under a threads or gevent
   pool, where `worker_process_init` never fires. Do not build that.
2. **An allow-list, so it fails closed.** A new instrumentor cannot leak; a
   new LLM instrumentation is dropped until its scope is listed, with one
   warning per scope so that is not silent.
3. **Tempo is untouched.** The project's own exporter is added unwrapped;
   infrastructure spans stay children of the LLM span there.
4. **Test what Langfuse's processor is handed, not a constant.** Replace
   `LangfuseSpanProcessor.on_end` with a recorder, run an `@observe`d function
   that emits a span from an `opentelemetry.instrumentation.psycopg` tracer,
   and assert the recorder got the LLM span only, in both creation orders
   (SDK default client first, yours first). Then disable the wrapper once and
   see the tests fail. The original test compared two constants and passed
   for the whole five weeks (NutriLens `backend/tests/test_tracing.py`).
5. **The one order that still matters: your provider must be the global one
   before any Langfuse client exists.** OpenTelemetry has the same
   first-wins rule as the SDK: `trace.set_tracer_provider` keeps the first
   provider and only logs a warning about the second. A Langfuse client
   created earlier (import time, `init_langfuse()` at the end of
   `settings.py`, an earlier `ready()`) finds no provider, installs a plain
   one, and yours is refused: the instrumentors then feed Langfuse
   everything and Tempo nothing. So after `set_tracer_provider(provider)`,
   check `trace.get_tracer_provider() is provider`; when it is not, log an
   error and do not instrument (NutriLens `init_tracing`, with a test). That
   stops your own instrumentors, not the leak: the foreign provider stays
   unfiltered, and any span another library emits on it still reaches
   Langfuse (reproduced in review). Tracing first is an invariant to keep,
   not a case the check handles.

**SDK v4 filters by default; v3 does not** (read in 4.0.1, 4.14.x and 4.15.x
and reproduced with in-memory exporters, 2026-10-10). v4 still adds its
processor to the app's global provider (`_client/resource_manager.py`,
`_init_tracer_provider`), but `LangfuseSpanProcessor.on_end` exports a span
only when `is_default_export_span` says so (`_client/span_filter.py`): scope
`langfuse-sdk`, or any attribute starting with `gen_ai`, or a scope in the
fixed LLM-instrumentation list (`openinference`, `litellm`,
`opentelemetry.instrumentation.openai`, `pydantic-ai`, …). Each span is judged
alone, so a psycopg span inside a Langfuse span is dropped; no env var changes
the filter, only `should_export_span=` on the client. Consequences:

- A v4 project with Tempo tracing needs no provider wrapper. It needs a
  **test**, because its safety is an SDK default: emit a span from an
  `opentelemetry.instrumentation.psycopg` tracer next to an LLM span and
  assert what the Langfuse exporter receives. Pin `langfuse>=4,<5`.
- Traces arrive unnamed with a dangling parent id when their root was a
  filtered Django or Celery span. Expected; name the trace from the LLM span.
- On v3, port the provider filter. Its allow-list must name every scope the
  project relies on: `langfuse-sdk`, plus `pydantic-ai` when
  `Agent.instrument_all()` feeds Langfuse.
- When writing any `SpanProcessor` wrapper, **subclass
  `opentelemetry.sdk.trace.SpanProcessor`**. The SDK calls `_on_ending(span)`
  on every registered processor at every span end; a duck-typed class with
  only `on_start` / `on_end` / `shutdown` / `force_flush` raises
  `AttributeError` there. EnaArchive went down on this on 2026-09-14, and three
  more projects carried the same class unnoticed, because their tests counted
  processors and never ended a span through the wrapper.

**A hand-made OTLP exporter to Langfuse has no filter at all.** The
"OTel exporter pattern" above (`OTLPSpanExporter` to
`/api/public/otel/v1/traces` in a `BatchSpanProcessor`) exports whatever the
provider carries. Rules for it:

- Do not make that provider global. Keep it private to PydanticAI:
  `Agent.instrument_all(InstrumentationSettings(tracer_provider=provider))`,
  built with `sampler=ALWAYS_ON`. Then no instrumentor added later can reach
  it (H2A Accountant sets it global: clean today only because nothing else
  emits spans).
- Do not run it NEXT TO the SDK. A project that has both the raw exporter and
  an SDK client (`@observe`, `get_client()`) sends every LLM span twice, and on
  v3 its own filter on the raw exporter hides that the SDK's processor is
  unfiltered. On v4 delete the raw exporter and keep `instrument_all()`: the SDK
  client is then the one export path. Do not create it at boot (`ready()` also
  runs in the Celery prefork main process and the client's threads do not
  survive the fork); it is created lazily by the first `@observe` /
  `get_client()`, so make sure every agent run passes through one of them (a
  `get_client()` in the run helper). `instrument_all()` at boot is fine before
  any provider exists: PydanticAI's tracer is a proxy that starts delivering
  once the SDK installs its provider (five projects fixed this way,
  2026-10-10).

**A lazily created client makes the leak intermittent, which hides it.**
EnaArchive (v3) filtered its raw exporter correctly and still leaked: the
SDK's default client is created by the first `@observe` call *in each
process*, and from then on that process exports everything until it is
recycled. It leaked for 42 hours after ten photo tasks ran, then stopped when
the Celery children hit `max-tasks-per-child`; 84 of its 85 traces were
periodic tasks with no LLM call. "Only two days of data" or "only some
workers" is this pattern, not a fix.

**Tests and local runs must not hold the production key.** A dev env file
with the production `LANGFUSE_*` values makes every pytest run write to the
production project: one project's whole volume (24,000 events a month, and
$95 of $96 "cost" from a fixture) was its test suite. Blank `LANGFUSE_*` and
set `LANGFUSE_TRACING_ENABLED=false` in the test settings or an autouse
fixture, give dev its own project or no keys, and never commit a key in a
prompt-upload script (three repositories had the production secret key in
tracked files).

**Prove it in production with one probe, not by waiting for traffic.** In a
one-off `python -c` inside the running worker container (`django.setup()`
installs the provider): open a span from a tracer named like an
instrumentation (`opentelemetry.instrumentation.celery`, kind CONSUMER, so the
no-orphan sampler keeps the children), run a real `SELECT` and one real,
cheap LLM call through the app's own traced function inside it, flush
(`get_client().flush()`), print the trace id. Then `GET
/api/public/traces/<id>` and list the observations by scope: only LLM scopes
must be there. `/api/public/v2/observations` lags by minutes; the trace
endpoint does not. Tempo's tail sampling may drop the probe trace, which is
not a failure.

**Query-string API keys end up in spans.** `httpx.get(url, params={"key":
api_key})` puts the key in `http.url` of the httpx span, which goes to Tempo
and, in a leak, to Langfuse. Send provider keys as headers
(`x-goog-api-key` for Gemini).

**Find out who used the quota** (read-only, works while suspended):

```
scripts/langfuse_usage.py --env <project env file> --since <billing period start>
scripts/langfuse_usage.py --env <…> --since 14d --scopes <a busy day>
```

It prints the key's project and organization, events per day, the share of
observations with no model, observations per trace, and with `--scopes` one
day split by instrumentation scope (v3 rows store it as `metadata.scope.name`,
v4 rows as the flat key `metadata["scope.name"]`; `resourceAttributes` /
`resourceAttributes.service.name` tells which service sent a row when two
share a project). For a project that only started recently it also prints the
rate over the days that have data. Reading it: about one model-less
observation per trace is the `@observe` wrapper and is fine; **more than ~5
observations per trace, mostly model-less, is infrastructure leaking**. The
org id in the mail's billing link identifies the organization; a key's
organization comes from `GET /api/public/projects`. Run it for every project
of that organization before blaming one. Events per LLM call are worth a look
too: a trace + an `@observe` wrapper span + a hand-made generation + PydanticAI's
`agent run` and `chat <model>` is 5 billable events for one call, and 2 is
enough (the trace and one generation). The plain list endpoints
(`/api/public/observations`, `/traces`) are limited to a few calls a minute;
`/api/public/metrics/daily` and `/api/public/v2/observations` (cursor, 1,000
per page) are the ones for volume.

## Cost attribution — tag every trace with a tenant

An untagged trace is spend you cannot bill, cap, or explain. **Every trace gets a
stable tenant identifier as `user_id`**, decided once per project (`client.slug`,
`radio.codename`, `org_id` — whatever the invoice is keyed on). Use the *same*
identifier in every repo and service that reports into one Langfuse project, or
each one becomes its own unmergeable slice.

**`user_id` / `session_id` / `tags` are first-class trace fields, not metadata.**
Writing `metadata["user_id"]` looks right, ships clean, and populates nothing —
`trace.userId` stays null and every cost-by-user dashboard buckets the spend
under **n/a**.

```python
# v4 — context manager, wraps the observation that will carry the attributes
from langfuse import propagate_attributes
with propagate_attributes(user_id=tenant, session_id=f"episode:{ep.uuid}", tags=[...]):
    with client.start_as_current_observation(as_type="generation", ...) as gen:
        ...

# v3 — no propagate_attributes; stamp from inside the observation
with client.start_as_current_observation(as_type="generation", ...) as gen:
    gen.update_trace(name="entity_extraction", user_id=tenant, session_id=f"news:{pk}")
```

- **`propagate_attributes` only affects the active span and spans opened after
  it** — it cannot retroactively stamp an already-open parent. Wrap the root as
  early as possible; wrapping late leaves earlier generations out of the
  aggregation for that attribute.
- **Threads break OTel context propagation.** If `run_sync` is isolated in a
  `ThreadPoolExecutor` for a wall-clock timeout, wrap *inside* the worker
  function — child threads start with empty context, so a parent-side wrapper
  leaves the model spans orphaned in a different trace.
- **A tenantless entry point is a design smell, not a tracing detail.** If the
  function genuinely has no tenant (preview/anonymous flows), tag it
  `user_id="anonymous-preview"` so it's a named bucket instead of n/a.

### `cost_details` key is `total`, not `total_cost`

```python
gen.update(usage_details={"input": n_in, "output": n_out},
           cost_details={"total": cost_from_provider})   # `total_cost` is silently ignored
```

The failure is invisible when your model *is* in Langfuse's price list: the real
per-call cost (e.g. OpenRouter's `x-openrouter-cost` header) gets dropped and
Langfuse back-fills a plausible estimate from token counts, so the dashboard
looks fine and is wrong. Verified on cloud.langfuse.com (July 2026) with a model
Langfuse can't price: `{"total_cost": 0.4242}` → `totalCost 0`;
`{"total": 0.4242}` → `totalCost 0.4242`. Test with a **bogus model name** —
that's what separates "my number landed" from "Langfuse guessed".

### Audit: find the unattributed spend

Don't eyeball the UI — bucket it. Read-only, works with any project's keys:

```python
import base64, collections, datetime, json, urllib.request
auth = base64.b64encode(f"{PK}:{SK}".encode()).decode()
frm = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
cost = collections.Counter()
for page in range(1, 11):
    url = f"{BASE}/api/public/traces?limit=100&page={page}&fromTimestamp={frm}"
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})))
    for t in d["data"]:
        cost[(t.get("name"), t.get("userId") or "<<N/A>>")] += t.get("totalCost") or 0
    if page >= d["meta"]["totalPages"]: break
for k, v in sorted(cost.items(), key=lambda x: -x[1])[:30]: print(f"{v:9.4f}  {k}")
```

Grouping by **(trace name, userId)** names the culprit function directly — a
single untagged code path shows up as one trace name dominating the `<<N/A>>`
rows. Timestamps must be `...Z`, not `+00:00` (the API 400s on the latter).
Traces that carry `@observe` but never open a generation show up as `$0` rows:
harmless noise, but they inflate the n/a *count* while contributing no cost —
read the cost column, not the row count.

## Testing agents (no network, ever)

Root `conftest.py`:
```python
import pydantic_ai.models
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False   # hard guarantee
```

- **TestModel** — auto-generates schema-valid output; smoke-tests plumbing:
  ```python
  from pydantic_ai.models.test import TestModel
  agent = Agent(TestModel(), output_type=CompanyProfileDraft)
  monkeypatch.setattr(module, "build_profile_agent", lambda: agent)
  ```
- **FunctionModel** — exact outputs for behavior tests (thresholds, branching):
  ```python
  from pydantic_ai.models.function import AgentInfo, FunctionModel
  from pydantic_ai.messages import ModelResponse, ToolCallPart
  def fake(messages, info: AgentInfo):
      return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=DRAFT_DICT)])
  agent = Agent(FunctionModel(fake), output_type=CompanyProfileDraft)
  ```
- Validator logic: test as plain pydantic (`CompanyProfileDraft(cpv_prefixes=["45000000","nada"])`), no agent needed.
- Prompt content: assert on the pure `build_*_prompt()` function output.

## Cost & rate-limit discipline (batch pipelines)

Anonymous/public endpoints that call a model (citizen RAG, "ask the archive") are a spend vector before they are a feature: per-IP+tenant `AnonRateThrottle` **and** a per-tenant daily budget counter (`cache.add` + `incr`, 429 beyond it), settings-driven (`RAG_ANON_RATE`, `RAG_DAILY_BUDGET_PER_TENANT`), tested so the throttled request never reaches the model (EnaArchive 2026-08-29).

- **LLM only where it adds value.** Deterministic prefilter first (SQL/FTS/rules) → LLM judges only the small candidate set. The whole pipeline must work with zero API keys; LLM layers go behind env flags (`LLM_SCORING_ENABLED=1`).
- **Cap calls per run** (`--max-llm-calls`, default ~200) and only score NEW items (unique-constraint idempotency) — reruns must be free.
- **Free-tier Gemini dies fast** (~5-10 RPM for generation): expect mid-batch 429s and transient TLS `ConnectError`s. Wrap each call in try/except, log, continue; never let one failure kill the batch. Use a paid key before enabling scoring in production.
- **Embeddings quota counts per TEXT, not per request**: `embed_content` with a 100-item batch burns 100 units of the free-tier `embed_content` quota (100/min for `gemini-embedding-001`). Design embedding backfills as resumable trickles (`embedding__isnull=True` queue + `--limit` per cron cycle) that break cleanly on 429 and continue next run.
- Serial `run_sync` is fine for small batches; for volume use async + `asyncio.Semaphore` (PydanticAI is async-first).

## Prompt patterns that earned their keep

- **User-steerable scoring**: store a free-text `matching_notes` field the user edits in the UI, inject into the judge prompt as `INSTRUCCIONES DEL USUARIO (máxima prioridad: si contradice esto, puntúa bajo)`. Lexical filters (keywords/negative keywords) can't express "we sell software, we don't produce content" — a prompt section can (verified: mismatched item dropped 30→5/100).
- Structured score output = `score: int (0-100)` + `reason: str` one-liner in the user's language — the reason doubles as UI explanation and debugging trail.
- Tell extraction agents explicitly: don't translate, don't invent URLs (only use URLs present in the input), be conservative when input is thin.

## Feeding websites to LLMs

- `httpx.get(url, timeout=20, follow_redirects=True)` + `lxml.html`: drop `script/style/nav/footer/noscript/svg/form`, `text_content()`, collapse whitespace, cap ~15k chars.
- **Harvest meta tags before stripping** (`<title>`, `meta[name=description]`, `og:*`) — JS SPAs render an empty body and meta is all you get. If extracted text < ~200 chars, warn and fall back to asking the user for a description.
- Truly JS-only sites need Playwright (sync API, `is_mobile=True` often gets simpler pages). Prefetch text and pass it to the agent — don't hand the agent a browser tool.
- PydanticAI's `WebFetchTool` respects robots.txt; blocked sites need the Playwright path.

## Django integration checklist

- [ ] If the project also traces to Tempo: the tracing provider is installed before any Langfuse client exists and filters what
      Langfuse's processor receives, and a test proves a database span is not exported to Langfuse (section "Langfuse is for
      LLM calls only")
- [ ] Otherwise: `init_langfuse()` at end of `settings.py` (guarded, idempotent)
- [ ] One documented tenant identifier, passed as `user_id` on **every** trace —
      the helper that opens the trace should require it, not default it to `None`
- [ ] `LLM_MODEL`, `LANGFUSE_*`, `GEMINI_API_KEY`/`ANTHROPIC_API_KEY` in `.env.example` + compose env
- [ ] Agents in `apps/<app>/agents.py` with builder functions + prompt builders
- [ ] `conftest.py` blocks real model requests
- [ ] A management command that exercises the full LLM flow end-to-end from the CLI (e.g. `make scan URL=...`) — invaluable for demos and debugging
- [ ] gunicorn `--preload` safety: no clients/agents created at module import (lazy builders make preload safe)
