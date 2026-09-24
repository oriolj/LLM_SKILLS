# Bench architecture — the pieces, their contracts, and skeleton code

Python-first (every LLM project in the estate is Python), framework-agnostic; the
Django variant is a plain app with a management command and no models. Two
implementations to copy from, both 2026-09:

- **enacast-ai** `backend/enacast_ai/bench/` — one feature (episode analysis, long
  transcripts), prompt-variant datasets, marker check, promotion to human voting.
  Doc: `backend/docs/BENCH.md`.
- **enacast** `enacast_backend/llm_bench/` — eight features behind one `Feature`
  interface (~1,900 lines incl. adapters), replay of production functions, call
  recorder. Doc: `docs/llm_bench.md`.

Start from the enacast one when the project has several features; it is the
generic shape this file describes.

## Layout

```
<app>/llm_bench/                 code (no DB models): schemas, paths, client, replay, judge, scoring,
                                 runner, leaderboard, dataset, pricing, features/{base,<one per area>}.py,
                                 management/commands/bench.py (or cli.py), tests/test_bench.py
bench/datasets/<feature>/<v>/    items.jsonl + manifest.json (+ assets/ for images)   — committed (private repo)
bench/results/<feature>/<v>/     <model-slug>__<effort>/<UTCstamp>.json + LEADERBOARD.md — committed
bench/results/<feature>/<v>/.cache/   per-item, per-phase cache — gitignored
bench/results/LEADERBOARD.md     index over every feature
```

Same commit that creates `bench/`: add it to `.dockerignore` (client data must never
enter an image) and the cache to `.gitignore`. Check the actual Dockerfile's
`COPY` lines — `.dockerignore` only matters if the build context includes the dir.

## Schemas (pydantic)

```python
class Item(BaseModel):            # one frozen case
    id: str                       # stable, readable: "<lang>-<bucket>-<uuid8>"
    feature: str
    language: str | None = None
    inputs: dict                  # EXACTLY what the production function needs (text, image paths, context)
    reference: dict | None = None # what production shipped for this case (model, prompt version, output)
    truth: dict | None = None     # human-labelled ground truth, when it exists
    meta: dict = {}               # strata (bucket, tenant kind), source ids — for slicing results

class Generation(BaseModel):
    model: str; effort: str | None
    output: Any | None = None     # None = failure (error, refusal, unparsable, truncated)
    error: str | None = None
    stats: dict = {}              # from the call recorder: tokens, reasoning tokens, cost, latency, provider

class ItemResult(BaseModel):
    id: str; language: str | None
    generation: Generation
    judges: dict[str, dict] = {}  # judge model -> {"scores": {...}, "invented": [...], "wrong": [...], ...}
    claims: dict | None = None    # claim check
    checks: dict[str, bool | None] = {}   # deterministic; None = not applicable
    truth_scores: dict = {}       # metrics against ground truth (F1, MAE, within-tolerance)

class RunResult(BaseModel):
    feature: str; dataset_version: str; model: str; effort: str | None
    prompt_fingerprint: str; rubric_version: int; judges: list[str]; judge_subset: dict
    started_at: str; git_sha: str | None
    items: list[ItemResult]; summary: dict
```

## The Feature interface

```python
@dataclass(frozen=True)
class Dim:
    name: str; weight: float; rubric: str     # rubric = how to deduct, in words the judge follows

class Feature:
    name, title, description                  # description is read by the judges: what the feature is FOR
    dims: tuple[Dim, ...]
    format_weight = 0.10                      # deterministic checks' share of the global score
    claims = False                            # run the claim-level hallucination check
    version = "v1"; rubric_version = 1; default_n = 40
    modalities = ("text",)                    # ("image", "text") for vision features

    production_model / production_effort     # read from the SAME table production reads — never a copy
    def prompt_fingerprint(self) -> str       # hash of the code/constants that shape the prompt
    def build(self, n, seed) -> (items, manifest_extra)      # read-only on a DB copy
    def generate(self, item, model) -> output | None          # calls the production function
    def checks(self, item, output) -> dict[str, bool | None]
    def judge_input(self, item) -> list[content parts]        # what the writer saw (text and/or images)
    def render_output(self, output) -> str
    def claim_source(self, item) -> str; def claim_text(self, output) -> str
    def truth_scores(self, item, output) -> dict               # optional, when items carry truth
```

`fingerprint(*objects)` = sha256 of `inspect.getsource` of the prompt-building
functions and prompt constants, first 12 chars. For prompts stored in Langfuse, the
fingerprint is the hash of the frozen prompt text in the manifest.

## Replay without touching production code

The bench calls the production function itself. What must differ is switched off
around it, in one context manager (`replay.bench_mode()`):

```python
@contextlib.contextmanager
def bench_mode(*, effort=None, frozen_prompts=None):
    none = mock.Mock(return_value=None)
    patches = [
        mock.patch.object(llm_module, "get_langfuse_client", none),   # no traces, no prompt fetches
        mock.patch("sentry_sdk.capture_exception", mock.Mock()),
        mock.patch.object(metrics, "increment", mock.Mock()),
        mock.patch("httpx.Client.send", recording_send),             # or requests.post, see below
    ]
    if effort:  patches.append(mock.patch.object(llm_module, "EFFORT_OVERRIDE", effort))
    if frozen_prompts:  patches.append(mock.patch.object(llm_module, "get_prompt", lambda name, **_: frozen_prompts[name]))
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"   # @observe and OTel instrumentation
    with contextlib.ExitStack() as stack:
        for p in patches: stack.enter_context(p)
        yield
```

Rules that came from real bugs:

- **A bench never writes to production Langfuse.** Disable the client *and*
  `LANGFUSE_TRACING_ENABLED` (the `@observe` decorator and PydanticAI/OTel
  instrumentation do not go through your client getter). Unit tests need the same
  fixture: on 2026-09-23 the enacast tests mocked the HTTP call but kept the real
  Langfuse keys, and a dozen fake `gpt-6-luna` generations landed in the production
  project, which looked like the first post-deploy traffic for a moment.
- **The model is an argument, not a monkeypatch.** Give every production function
  a `model=` parameter defaulting to the feature table
  (`def extract_tags(text, model: str = feature_model("tags"))`). A one-line refactor,
  behaviour-preserving, and it is what makes replay honest.
- **Split "build the prompt" from "call the model" from "save the result"** where
  they are fused (`build_glossary_prompt` → `request_glossary` → save). The bench
  replays the middle; production keeps calling all three.
- **Freeze the prompt source, not the prompt**, when the prompt is assembled from
  data (the enacast glossary dataset froze assembled prompts, so a new prompt
  version could not be benched on it; it had to be rebuilt storing the source).
  When the prompt lives in Langfuse, freeze the fetched text into the manifest and
  replay it (`frozen_prompts`) so a Langfuse edit does not silently change a rerun.

### Call recorder (real cost and tokens per generation)

Wrap the transport the production code uses and record per thread:
model, status, latency, prompt/completion/reasoning tokens, **cost**, provider,
finish reason, BYOK flag. Transports seen in the estate:

| Production calls via | Patch |
|---|---|
| `requests.post` to OpenRouter | `mock.patch("requests.post", recording_post)` |
| `httpx` (OpenAI SDK, PydanticAI, google-genai all use it) | `httpx.Client.send` / `httpx.AsyncClient.send` |
| PydanticAI | also `result.usage()` after the run; cost is not in it — compute from the price table |
| google-genai direct | `response.usage_metadata` (prompt/candidates/thoughts token counts); no cost field |

Cost, in order of trust: OpenRouter body `usage.cost_details.upstream_inference_cost`
(the real model cost, **also for BYOK calls**, where `usage.cost` is 0) → `usage.cost`
→ tokens × list price from the OpenRouter catalogue (`GET /api/v1/models`,
`pricing.prompt|completion|image|internal_reasoning`, cached daily in `pricing.py`).
OpenRouter sends no cost header and no `usage.total_cost` (verified 2026-09-23).

### Judges and candidates through OpenRouter

The bench's own calls (judges, claim extraction, candidate models the product does
not support natively) go through one small client:

- strict JSON schema output (`response_format: {type: json_schema, strict: true}`),
  with the pydantic schema closed: every object `additionalProperties: false`,
  every property required, `$ref`s inlined (OpenAI strict mode rejects the rest);
- `temperature 0`, `reasoning: {effort: low}` for judges unless the rubric needs more;
- 3 retries on 429/5xx/timeouts with jittered backoff; a judge failure is recorded
  as a missing judgement, never as a zero score;
- a model the OpenRouter **account** cannot reach (privacy setting excludes all its
  endpoints) raises before any result file is written — 100 failures in one second
  is a broken setup, not a score.

## Runner

```
for item in dataset (threads, --workers 4):
    gen    = cache("gen", item, model, effort, prompt_fp)   or generate under bench_mode + CallRecorder
    checks = feature.checks(item, gen.output)                (always recomputed: free)
    post   = production post-processing (quote check, validators) — same code path as production
    judges = cache("judge", item, judge, rubric_version, output_hash, context_version) or rubric_score(...)
    claims = cache("claims", ...) when feature.claims
    truth  = feature.truth_scores(item, output) when item.truth
write results/<feature>/<v>/<model-slug>__<effort>/<UTCstamp>-<tag>.json ; regenerate leaderboards
```

- **Per-phase cache keyed on everything that changes the answer** (item, model,
  effort, prompt fingerprint for generations; judge, rubric version, output hash,
  judge-context version for judgements). Ctrl-C and rerun resumes; `--rescore`
  keeps outputs and re-judges; changing a rubric re-judges only.
- **A cached result is not money spent.** A re-run's summary re-counts cached
  judgements, so summing result files overstates spend (enacast-ai: files said
  ≈ $579, the key billed less). Spend comes from the provider's key counters.
- `--dry-run` (items × estimated tokens × catalogue price, per phase),
  `--limit N`, `--only-language`, `--items a,b`, `--tag`, `--no-progress` for logs.
- Failure = output None, exception, refusal, unparsable, `finish_reason=length`:
  scored 0 on every dimension and counted; the run continues.

## CLI and Makefile

```
make bench-features                                # features, production model/effort, dataset state
make bench-build [FEATURE=x] [N=40]                # freeze from the local DB copy (read-only)
make bench-run [FEATURE=x] [MODEL=production|vendor/model] [EFFORT=production|minimal|low|medium|high] [ARGS=…]
make bench-reference                               # score what production actually shipped (no generation)
make bench-leaderboard
make bench-compare A=<result|row> B=<result|row>   # per-dimension deltas + the items that moved most
```

`MODEL=production` / `EFFORT=production` = each feature's own production setting,
so `make bench-run` with no arguments is the baseline of everything.

## Tests (no network)

- replay isolation: inside `bench_mode` no Langfuse client, tracing env off, effort
  override applies, and it is restored after;
- the call recorder keeps the real cost of a BYOK call (`cost: 0` +
  `upstream_inference_cost`);
- strict schema: every object closed, no `$defs`;
- each feature's deterministic checks on a passing and a failing output;
- scoring: judges + claims + checks blend as documented; a failed generation is 0;
- a full run on a fake feature with mocked judges: result file written, cache hit on
  rerun (judge call count unchanged), leaderboard mentions the model.

The enacast `llm_bench/tests/test_bench.py` has all of these in ~150 lines.
