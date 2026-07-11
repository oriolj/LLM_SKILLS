---
name: pydantic-ai-langfuse
description: Implement LLM features in Python with PydanticAI + Langfuse observability. Use when adding LLM calls to any Python/Django project, integrating PydanticAI agents, wiring Langfuse tracing, testing agents without hitting real models, choosing model strings, debugging "Unknown provider" / instrument errors, fetching websites as LLM input, or controlling LLM costs in batch pipelines. Covers PydanticAI 2.x API changes, OTel→Langfuse setup, TestModel/FunctionModel testing, Django-specific OOM traps, SPA scraping, and rate-limit-safe batch scoring.
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

- **Model strings** are `provider:model` from env (e.g. `LLM_MODEL=google:gemini-3.5-flash`, `anthropic:claude-haiku-4-5`). API keys via env: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.
- **Build agents in a function, not at import time.** Import-time `Agent(...)` couples module import to provider config, breaks in keyless environments (CI), and makes test override painful. A `build_*_agent()` function is trivially monkeypatched in tests.
- **Build prompts in a separate pure function** (`build_scoring_prompt(profile, item) -> str`) so prompt content is unit-testable with zero LLM calls.
- **Validators as guardrails**: normalize LLM output in `@field_validator` (dedupe, regex-check codes, strip junk) instead of trusting the model or post-processing at call sites.
- Deps extras matter: `pydantic-ai-slim[google,anthropic]` — the `google` extra brings `google-genai`.

## PydanticAI 2.x breaking changes (hit in the wild)

| Old (≤1.x) | 2.x | Symptom if wrong |
|---|---|---|
| `google-gla:gemini-…` | `google:gemini-…` | `ValueError: Unknown provider: google-gla` |
| `Agent(..., instrument=True)` | `Agent.instrument_all()` (global, call once at startup) | `TypeError: unexpected keyword argument 'instrument'` |

When touching an unfamiliar pydantic-ai version, introspect before writing code:
`python -c "import inspect, pydantic_ai; print(pydantic_ai.__version__); print(inspect.signature(pydantic_ai.Agent.__init__))"`

## Langfuse tracing (OTel exporter pattern)

One init function, called once at process start (Django: end of `settings.py` — covers gunicorn, manage.py commands, and cron jobs alike). **No-op without keys** so dev/test never need Langfuse:

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

- **LLM only where it adds value.** Deterministic prefilter first (SQL/FTS/rules) → LLM judges only the small candidate set. The whole pipeline must work with zero API keys; LLM layers go behind env flags (`LLM_SCORING_ENABLED=1`).
- **Cap calls per run** (`--max-llm-calls`, default ~200) and only score NEW items (unique-constraint idempotency) — reruns must be free.
- **Free-tier Gemini dies fast** (~5-10 RPM): expect mid-batch 429s and transient TLS `ConnectError`s. Wrap each call in try/except, log, continue; never let one failure kill the batch. Use a paid key before enabling scoring in production.
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

- [ ] `init_langfuse()` at end of `settings.py` (guarded, idempotent)
- [ ] `LLM_MODEL`, `LANGFUSE_*`, `GEMINI_API_KEY`/`ANTHROPIC_API_KEY` in `.env.example` + compose env
- [ ] Agents in `apps/<app>/agents.py` with builder functions + prompt builders
- [ ] `conftest.py` blocks real model requests
- [ ] A management command that exercises the full LLM flow end-to-end from the CLI (e.g. `make scan URL=...`) — invaluable for demos and debugging
- [ ] gunicorn `--preload` safety: no clients/agents created at module import (lazy builders make preload safe)
