# TikHub Service (`tikhub` SDK)

The `tikhubAction` node wraps the **official TikHub Python SDK**
(`pip install tikhub`) for [api.tikhub.io](https://api.tikhub.io), a
pay-per-request scraping API covering TikTok, Douyin, Instagram, YouTube,
Twitter/X, Xiaohongshu, Bilibili, Kuaishou, Weibo, Reddit, Threads,
LinkedIn, Zhihu and more (~1,100 methods in the pinned SDK). One
self-contained plugin folder at
[`server/nodes/scraper/tikhub_action/`](../server/nodes/scraper/tikhub_action/).

The SDK is auto-generated from TikHub's `openapi.json`: every OpenAPI tag
becomes a resource attribute on the client (`douyin_web`,
`tiktok_app_v3`, `instagram_v3`, `hybrid_parsing`, `tikhub_user`, ...)
and every route becomes a coroutine method whose keyword-only
parameters mirror the query / body schema. The SDK's only logic is a
retry policy and a typed exception hierarchy; it returns the raw JSON
envelope `{"code": 200, "router": "...", "params": {...}, "data": {...}}`.
TikHub's own CLI has four commands (`health`, `fetch <url>`, `user info`,
`user usage`), so the node is the "flattened CLI": one `call` operation
addressed by the SDK's own `resource.method` id, plus discovery, hybrid
URL fetch, and account ops. **Nothing is vendored** - the endpoint index
is introspected from the installed SDK at runtime, so bumping the pin is
how new endpoints arrive.

| | |
|---|---|
| Node type | `tikhubAction` (palette group `scraper`, dual-purpose AI tool `tikhub_action`; visible in normal mode) |
| Operations | `call` / `list_endpoints` / `fetch_url` / `account` |
| SDK pin | `tikhub>=2.1.2,<3` in `server/pyproject.toml` (resources regenerate between minors; `<3` caps the surface) |
| Auth / probe | `TikHubCredential(ApiKeyCredential)` - bearer key; declarative httpx probe against `GET /api/v1/tikhub/user/get_user_info` (never `/health/check`, which is unauthenticated) |
| Task queue | `TaskQueue.REST_API` |
| Output | `_shape(operation, **fields)` - `{operation, endpoint, path, data, code, router, cost_usd}` for calls; `{operation, platform, count, total, endpoints[]}` for listing; `{operation, account, usage}` for account. `None` fields dropped, `{}` / `[]` kept (an empty answer from TikHub is real) |
| Cost | Flat `$0.001` per successful request (`pricing.json: api.tikhub`), recorded by `track_tikhub_usage` into `api_usage_metrics`; `list_endpoints` never bills, `account` bills at `0.0` |
| Tests | [`server/tests/nodes/test_tikhub.py`](../server/tests/nodes/test_tikhub.py) (`pytestmark = node_contract`; `pytest --collect-only -q` for the live count) |
| Paired skill | [`server/skills/web_agent/tikhub-skill/SKILL.md`](../server/skills/web_agent/tikhub-skill/SKILL.md) |
| Node card | [`docs-internal/node-logic-flows/web_automation/tikhubAction.md`](./node-logic-flows/web_automation/tikhubAction.md) |

## Folder map

```
server/nodes/scraper/
├── _credentials.py              # ApifyCredential + TikHubCredential (probe + _handle_probe_response)
├── tikhub.svg                   # Credential brand icon -> /api/schemas/credentials/tikhub/icon
└── tikhub_action/
    ├── __init__.py              # TikHubActionParams / TikHubActionOutput / TikHubActionNode
    │                            # (4 @Operations), _shape, register_option_loader("tikhubEndpoints"),
    │                            # register_output_schema. Must NOT import `tikhub` at module import.
    ├── _sdk.py                  # Everything that touches `tikhub`, lazily inside functions:
    │                            # make_client, EndpointInfo/ParamInfo, endpoint_index (cached),
    │                            # resolve_endpoint, bind_params, to_plain, raise_user_error,
    │                            # load_tikhub_endpoints, track_tikhub_usage, PLATFORMS,
    │                            # _MAX_RETRIES / _TIMEOUT
    ├── meta.json                # {"color": "#ff79c6"} (scraper group colour, matches apify_actor)
    └── icon.svg                 # Node brand mark
```

Config touched outside the folder: `server/config/credential_providers.json`
(`providers.tikhub`, category `scrapers`, `usage_service: "tikhub"`),
`server/config/pricing.json` (`api.tikhub` + `operation_map.tikhub`),
`server/config/node_allowlist.json` (`tikhubAction` in `enabled_nodes`),
`server/nodes/visuals.json` (`"tikhubAction": {"skill": "tikhub-skill"}`),
`server/tests/fixtures/tool_names_snapshot.json`
(`"tikhubAction": "tikhub_action"`). `server/nodes/__init__.py` is not
touched - pkgutil discovery picks up the folder, and `_sdk.py` is skipped
by the underscore rule.

## Why the SDK, and why import it lazily

Two paths were on the table: hand-rolled httpx against a vendored
endpoint list, or the official SDK with runtime introspection. The SDK
won because the endpoint surface is the product (TikHub adds and retires
routes monthly) and a vendored index would rot within weeks; the SDK pin
is the single knob that tracks upstream. The costs are (a) `typer` +
`shellingham` arrive as transitive deps for the SDK's own CLI (click /
rich were already present; nothing imports typer at runtime), and (b)
resources regenerate between minors, so anything that names an endpoint
(the `PLATFORMS` tuple, the skill cheat sheet, the tool description) can
drift - see "Invariants".

`tikhub` is imported **only inside functions in `_sdk.py`**. The plugin
module itself must import cleanly with `sys.modules["tikhub"] = None`
(test-locked in a subprocess), for the same reason the LLM providers keep
their SDK imports lazy: plugin registration runs at boot for every node
whether or not the operator ever uses TikHub, and an SDK import failure
must degrade to a `NodeUserError` at execution time
("The 'tikhub' package is not installed - run `uv sync` in server/"),
never to a boot failure or a missing node.

## Dispatch - reflective `resource.method`

`call` never names an SDK method in code. The flow is:

1. `resolve_endpoint(raw)` - accepts `resource.method`, `resource/method`,
   a full `/api/v1/...` path, or a URL containing one (via `_BY_PATH`).
   Unknown input raises `NodeUserError` with up to five
   `difflib.get_close_matches` suggestions and the hint to run
   `list_endpoints`. No network call happens before resolution succeeds.
2. `make_client(ctx)` - see "Credential" below. Used as
   `async with` per operation; `AsyncTikHub(api_key=..., timeout=_TIMEOUT,
   max_retries=_MAX_RETRIES)`. `http_client` is **not** passed: respx
   patches httpx globally and the SDK's own tests are respx-based, so the
   contract tests intercept the SDK's internal client.
3. `fn = getattr(getattr(client, info.resource), info.method)`.
4. `bind_params(info, fn, params)` - `inspect.signature(fn).bind(**params)`
   before calling. A `TypeError` becomes
   `NodeUserError(f"{endpoint} rejected params: {e}. Accepted: aweme_id (str, required), ...")`
   so the LLM sees the accepted names without burning a request.
5. `result = to_plain(await fn(**params))` inside
   `try/except TikHubError -> raise_user_error(e, endpoint)`.
   `to_plain` calls `model_dump(mode="json")` if the SDK ever returns
   models, unwraps `data` / `code` / `router`, and raises `NodeUserError`
   when the in-body `code` is an int >= 400 (the SDK only raises on HTTP
   status; TikHub sometimes answers 200 with `code: 400` in the body).
6. `track_tikhub_usage(ctx, "call", info.path)` after success only.
7. `_shape("call", endpoint=..., path=..., data=..., code=..., router=..., cost_usd=...)`.

`fetch_url` is the same path hard-wired to
`hybrid_parsing.video_data(url=..., minimal=...)`. `account` calls
`tikhub_user.get_user_info()` + `tikhub_user.get_user_daily_usage()` and
returns them as `account` / `usage`, tracked at zero cost.

### Batch POST endpoints

A few SDK methods take a single `body: list[Any]` keyword (e.g.
`douyin_web.fetch_multi_video`). They ride the same `params` field -
`{"body": [...]}` - and bind like any other keyword; nothing in the node
special-cases HTTP method.

## Runtime introspection - `endpoint_index()`

Module-level `_INDEX` cache behind an `asyncio.Lock`, built once per
process on first use (`list_endpoints`, the dropdown loader, or the first
`call`). Cost is ~100-300 ms for ~1,100 methods.

- **Resources**: a throwaway `async with AsyncTikHub(api_key="introspection")`
  (no network); iterate `vars(client)` and keep non-underscore attributes
  that are `tikhub.resources._base.AsyncResource` instances (fallback:
  `type(obj).__module__.startswith("tikhub.resources")`).
- **Methods**: `inspect.getmembers(type(obj), inspect.iscoroutinefunction)`,
  skipping `_`-prefixed names.
- **Params**: the `KEYWORD_ONLY` parameters of `inspect.signature(fn)`.
  Annotations are strings (the generated modules use
  `from __future__ import annotations`) and are kept as display text -
  no `eval_str`. `required = default is Parameter.empty`.
- **HTTP method + path**: regex over `inspect.getdoc(fn)`:
  ``r"``(GET|POST|PUT|PATCH|DELETE)\s+(/\S+?)``"`` - the generated
  docstrings carry the route literal as their last line
  (verified on 2.1.2: every one of the 1,100+ methods matched).
  Fallback: the same regex over `inspect.getsource(fn)` guarded by
  `try/except (OSError, TypeError)`; else `path=None` (display only -
  such an endpoint can still be called by id, just not by path).
- **Summary**: first docstring line; the generated summaries are
  bilingual (`"获取单个作品数据/Get single video data"`), so the option
  label prefers the English part after the last `/`.
- **Record**: `EndpointInfo(endpoint="douyin_web.fetch_one_video", resource,
  method, platform=resource.split("_")[0], http_method, path, summary,
  params=(ParamInfo(name, type, required), ...))`, sorted by `endpoint`,
  plus `_BY_ENDPOINT` and `_BY_PATH` dicts.

`PLATFORMS` is a static tuple - `("all", "tiktok", "douyin", "instagram",
"youtube", "twitter", "xiaohongshu", "bilibili", "kuaishou", "weibo",
"reddit", "threads", "linkedin", "zhihu", "toutiao", "xigua", "wechat",
"lemon8", "pipixia", "hybrid", "tikhub")` - because it feeds a Pydantic
`Literal` that must exist at class-definition time, before any SDK import.
Filter rule is `info.platform == platform`, i.e. the first underscore
segment of the resource name. A test asserts every value except `all`
matches at least one live resource, so an SDK rename fails loudly rather
than producing an empty dropdown.

### The dynamic dropdown

`register_option_loader("tikhubEndpoints", load_tikhub_endpoints)`; the
`endpoint` field declares `dynamicOptions: True`,
`loadOptionsMethod: "tikhubEndpoints"`, `loadOptionsDependsOn: ["platform"]`.
The loader wraps `endpoint_index()` in `try/except Exception ->
logger.warning + []` (an SDK problem must never break the parameter
panel). For `platform == "all"` it returns `[]` rather than ~1,000 options
- the UI prompts the user to pick a platform, while the LLM path still
accepts any id as free text because `endpoint` is `str`, not a `Literal`.
Options are `{"value": e.endpoint, "label": e.endpoint,
"description": f"{summary} - {http_method} {path}"}`.

## Credential and probe

```python
class TikHubCredential(ApiKeyCredential):
    id = "tikhub"; display_name = "TikHub"; category = "Scrapers"
    key_name = "Authorization"; key_location = "bearer"
    docs_url = "https://docs.tikhub.io"
    probe_url = "https://api.tikhub.io/api/v1/tikhub/user/get_user_info"
```

- **Runtime resolution** goes through
  `await TikHubCredential.resolve(user_id=ctx.credential_customer_id)` -
  the sanctioned SDK-node path from the `services/plugin/connection.py`
  docstring. A missing key raises the annotated `PermissionError`, which
  `BaseNode.execute` turns into the `PermissionDeniedError` envelope plus
  the `credential.api_key.runtime_failed` broadcast (the modal badge
  flips red). This deliberately does NOT copy Apify's "return None then
  `NodeUserError`" shape, which loses the structured envelope.
- The key is passed to `AsyncTikHub(api_key=...)` explicitly so an ambient
  `TIKHUB_API_KEY` in the server's environment can never authenticate a
  node implicitly.
- **Probe** is the declarative httpx path of `ApiKeyCredential` (not the
  SDK) so the credentials modal keeps working even if the SDK import
  fails. `_handle_probe_response` reads `user_data.email / balance /
  free_credit` and `api_key_data.api_key_name` defensively (field names
  were inferred from the CLI's `user info` output; absence is tolerated)
  into `ProbeResult(extra=...)`, message
  `"TikHub key validated - {email} (balance ${balance})"`. A 401 surfaces
  through the base `raise_for_status` path.

Catalogue entry (`credential_providers.json`, same shape as `apify`, no
`validate_as`): `kind: "apiKey"`, one required password field `apiKey`
with placeholder "TikHub API key (user portal -> API keys)", icon ref
`/api/schemas/credentials/tikhub/icon`, `usage_service: "tikhub"` so the
API usage panel groups the rows.

## Error mapping - `raise_user_error(e, endpoint)`

Exception classes are imported lazily from `tikhub`. Every mapped case
becomes a `NodeUserError` (one WARN line, no traceback, structured
envelope). `request_id` is appended when the SDK exposes it.

| SDK exception | HTTP | User message (shape) | Why this shape |
|---|---|---|---|
| `TikHubAuthError` | 401 | `TikHub rejected the API key (401) while calling {endpoint}. Update it in Credentials -> TikHub.` | Not retryable; points at the fix |
| `TikHubPermissionError` | 403 | `TikHub refused {endpoint} (403): {detail}. The key may lack access ... or the account balance may be exhausted - run operation=account to check.` | 403 means EITHER the key's plan excludes the endpoint OR balance is exhausted; the node cannot tell which, `account` can |
| `TikHubRateLimitError` | 429 | `TikHub rate-limited {endpoint} (429); retry after {retry_after}s. Each endpoint allows about 10 requests/s.` | 10 req/s per endpoint path; SDK already retried with backoff |
| `TikHubBadRequestError` / `TikHubValidationError` | 400 / 422 | `TikHub rejected the request to {endpoint} ({status}): {detail}. Response: {body}` (body truncated to ~500 chars; `TikHubValidationError` reads `unparseable response`) | The detail is what the LLM needs to fix the args |
| `TikHubNotFoundError` | 404 | `TikHub returned 404 for {endpoint}: {detail}. The route or the requested resource does not exist ...` | Route retired or resource id gone; points at `list_endpoints` |
| `TikHubUpstreamError` / `TikHubServerError` / `TikHubConnectionError` | 5xx / network | `TikHub upstream error while calling {endpoint} (HTTP {status}): {detail}. Retries were exhausted - try again later.` | SDK already retried; a WARN envelope beats a traceback plus Temporal re-runs on a non-idempotent paid call |
| `TikHubFeatureRemovedError` / `TikHubConfigError` | - | `str(e)` | SDK-side messages are already user-facing |
| anything else | - | propagates | Genuine bugs keep the full traceback through `BaseNode.execute` |

In-body errors (HTTP 200, `code >= 400` in the JSON) are raised by
`to_plain` with the body's message. Pre-flight failures (`Unknown TikHub
endpoint ...`, `... rejected params ...`) are raised before any HTTP call.

## Cost tracking

`pricing.json`:

```json
"api": { "tikhub": { "_description": "TikHub pay-per-request (non-2xx not billed)",
                     "_source": "https://tikhub.io/pricing", "_updated": "2026-09",
                     "request": 0.001, "meta": 0.0, "_default": 0.001 } },
"operation_map": { "tikhub": { "call": "request", "fetch_url": "request", "account": "meta" } }
```

Both halves are required - `calculate_api_cost` returns `0` silently on a
missing `operation_map` line. The `$0.001` figure is TikHub's list price
for the common tier; per-endpoint pricing exists (`tikhub_user.get_endpoint_info`
returns it) but a flat rate was the user's decision (2026-09-04) because
the per-endpoint table changes independently of the SDK and would need
its own refresh loop.

`track_tikhub_usage(ctx, action, endpoint_path)` in `_sdk.py` is modelled
on `track_twitter_usage` (`server/nodes/twitter/_base.py`):
`get_pricing_service().calculate_api_cost("tikhub", action, 1)` then
`get_database().save_api_usage_metric({session_id, node_id, workflow_id,
service: "tikhub", operation, endpoint: <REST path>, resource_count: 1,
cost})`, wrapped in `try/except -> logger.warning` (a metrics failure
never fails a paid call that already succeeded). Called **only after a
successful call**, never for `list_endpoints`, never after a 4xx/5xx
(TikHub does not bill those either). Returns `total_cost` for the
`cost_usd` output key. The `cost=` metadata on each `@Operation` is
dormant - the manual tracker does the work, because the framework's
cost hook fires per operation and cannot know whether the call was
billed.

## Team visibility

A team lead (`orchestrator_agent` / `ai_employee`) never sees a teammate's
tools directly: the `delegate_to_*` tool that carries `tool_description` is
hidden from the lead's model. What the lead sees is the roster line
`collect_teammate_connections()` renders per teammate
(`services/plugin/edge_walker.py::format_teammate_roster_line`), which
lists the teammate's connected tools by the plugin `description` ClassVar
and its Master Skill entries by SKILL.md description. So when `tikhubAction`
hangs off a subagent, the lead's prompt reads
`- web_1: Web Agent (aiAgent) - tools: TikHub (Scrape TikTok, Douyin, ...); skills: tikhub-skill (...)`.
Keep `TikHubActionNode.description` and the skill's frontmatter
`description` written as capability sentences for that reason. See
[agent_teams.md](./agent_teams.md).

## SDK version-bump recipe

1. Edit the pin in `server/pyproject.toml` (`"tikhub>=2.1.2,<3"` - keep
   the `<3` cap unless you have re-verified the introspection contract
   against the new major), then `cd server && uv sync`.
2. Smoke the two things the node relies on:
   ```
   uv run python -c "import sys, tikhub; print(tikhub.__version__, 'typer' in sys.modules)"   # version, False
   uv run python -c "import sys; import nodes.scraper.tikhub_action; print('tikhub' in sys.modules)"  # False
   uv run python -c "import asyncio; from nodes.scraper.tikhub_action._sdk import endpoint_index; ix=asyncio.run(endpoint_index()); print(len(ix), ix[0])"
   ```
   Eyeball the count against the previous release (2.1.2 indexes ~1,100
   methods across 53 resources). A large drop means a resource stopped
   being an `AsyncResource` instance attribute or the docstring route
   convention changed - fix the introspection fallbacks before shipping.
3. Run the two drift guards from the contract suite:
   `uv run pytest tests/nodes/test_tikhub.py -k "platforms or skill_endpoint"`
   (test 12: every `PLATFORMS` value except `all` matches at least one
   live resource and the index exceeds 500 entries; test 18: every
   backticked `x.y` id in `SKILL.md` resolves in the live index). Then
   the full file: `uv run pytest tests/nodes/test_tikhub.py -v`.
4. If test 18 fails, update the skill's cheat sheet and the ids in the
   node's `tool_description` - prefer the highest `_vN` variant the new
   SDK exposes. If test 12 fails, adjust `PLATFORMS`.
5. `uv run ruff check nodes/scraper tests/nodes/test_tikhub.py` and
   `python -m cli docs nodes --check` from the repo root.

## Invariants locked by `test_tikhub.py`

Registration (type / tool name / group / credentials / `usable_as_tool` /
both handles visible - `usable_as_tool = True` auto-hides both handles
unless `hide_input_handle = False` and `hide_output_handle = False` are
declared explicitly); `get_option_loader("tikhubEndpoints")` registered;
`tikhub` in `CREDENTIAL_REGISTRY`; tool schema has no `$defs`. `call`
sends the bearer header and the keyword args as query params, drops
`None` args, unwraps `data`. `params` accepted as a JSON string and as
`""` from the panel (`coerce_blank_params`). REST-path alias resolves.
Unknown endpoint and unknown kwarg fail **before** any HTTP call. Missing
key produces `error_type == "PermissionDeniedError"` with
`credential.provider == "tikhub"`. 401 / 403 / 429 (+ `Retry-After`) /
422 detail / 502 map to `NodeUserError`; HTTP 200 with in-body `code: 400`
is a user error. `fetch_url` forwards `url` + `minimal`; `account` makes
two GETs. `list_endpoints` filters by platform + search and reports
`douyin_web.fetch_one_video` as `GET` with its path and a required
`aweme_id`. Every `PLATFORMS` value except `all` matches a live resource;
index length > 500. The loader returns options for a platform and `[]`
when `tikhub` is missing. The plugin imports in a subprocess with
`sys.modules["tikhub"] = None`, and importing the plugin does not import
`tikhub`. Probe 200 yields `ProbeResult.valid` + `extra["balance"]`;
401 raises. Catalogue / assets present (`credential_providers.json`
entry, `visuals.json` skill, `node_allowlist.json`, `SKILL.md`,
`icon.svg`, `tikhub.svg`, `meta.json` colour). `save_api_usage_metric`
awaited once with `service == "tikhub"` after a 2xx, not for
`list_endpoints`, not after a 4xx. Every skill endpoint id resolves.

## Risks

- **SDK churn.** Resources regenerate between minors; `PLATFORMS`, the
  skill cheat sheet and the tool description can rot. Guarded by tests 12
  and 18 and the `<3` cap - the bump recipe above is the maintenance
  loop.
- **Introspection assumptions.** Resources must be `AsyncResource`
  instance attributes and docstrings must carry the route literal. Both
  have fallbacks (module-name check; `getsource` regex; `path=None`), but
  a generator rewrite could still shrink the index - hence the "eyeball
  the count" step.
- **First-use latency.** The first `list_endpoints` / dropdown open
  reflects ~1,100 methods (~100-300 ms), cached per process; a worker
  restart pays it again.
- **Probe field names** were inferred from the CLI's output, not from a
  schema; extraction is defensive and should be tightened after a
  real-key run.
- **403 ambiguity.** TikHub uses 403 for both "not in your plan" and
  "balance exhausted"; the message points the user at `account` rather
  than guessing.
- **Flat pricing is an approximation.** Some endpoints cost more than
  `$0.001`; the recorded cost is a floor, and the balance reported by
  `account` is the truth.
- **New transitive deps.** `typer` and `shellingham` arrive for the SDK's
  own CLI; nothing in OpenCompany imports them and no version conflicts
  were found at 2.1.2.
