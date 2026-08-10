"""Contract for LLMTR, the second gateway provider.

A *gateway* fronts many vendors behind one key and names models
``vendor/model``. OpenRouter was the only one; LLMTR is the second, and it
exposes three behaviours a single-vendor provider never has. Each was found
by testing against the live service, and each silently breaks calls if it
regresses — hence a test rather than a comment.

1. **The catalogue is mixed-modality.** ``GET /v1/models`` returns every row
   LLMTR serves: chat, embeddings, image, video, rerank, audio, plus
   Responses-only models. Only the ``CHAT_COMPLETIONS`` rows may reach
   ``/v1/chat/completions``; serving the rest in a chat-model dropdown means
   a user can pick an embedding model and get an opaque 404 at run time.

2. **The model-list route is public.** It answers 200 with no key and 200
   with an invalid key, so "the listing worked" proves nothing about the
   credential. This is the exact inverse of Sarvam (no listing route at all,
   see test_model_listing_fallback.py) and needs the opposite remedy: a real
   1-token completion in ``LLMTRCredential._probe``.

3. **Wire shape belongs to the vendor; thinking belongs to the gateway.**
   ``openai/o4-mini`` refuses ``max_tokens`` + ``temperature`` no matter who
   proxies it, so the shape must come from the vendor's block. But LLMTR
   normalizes reasoning onto ``reasoning_effort`` for every vendor and
   rejects it outright on models it hasn't enabled it for, so the vendor's
   *native* thinking type must NOT be adopted — emitting Anthropic's or
   Moonshot's proprietary ``extra_body`` through the gateway is undefined,
   and switching OpenAI rows to ``effort`` turns a working call into a 400
   the moment a user ticks "thinking".

No test here touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Import the openai SDK BEFORE any test patches ``httpx.AsyncClient``.
# ``openai._base_client`` declares ``class AsyncHttpxClientWrapper(httpx.AsyncClient)``
# at module scope, so if the SDK is first imported while that name is patched
# the wrapper permanently inherits from the mock — every later
# ``AsyncOpenAI(...)`` in the same process then fails, including ones in
# unrelated tests. Eager import binds the class to the real httpx type.
import openai  # noqa: F401 — import-order guard, see above
import services.llm  # noqa: F401 — side-effect import populates the registry
from services.llm.config import is_model_valid_for_provider
from services.llm.providers.llmtr import CHAT_OPERATIONS, LLMTRProvider
from services.llm.providers.openai import OpenAIProvider
from services.llm.registry import get_provider
from services.model_registry import _ROUTER_PROVIDERS


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _llm_defaults() -> Dict[str, Any]:
    return json.loads((CONFIG_DIR / "llm_defaults.json").read_text(encoding="utf-8"))


def _provider() -> LLMTRProvider:
    with patch("openai.AsyncOpenAI"):
        provider = LLMTRProvider("llmtr-test-key")
    provider._client = MagicMock(name="AsyncOpenAI")
    return provider


# ---------------------------------------------------------------------------
# 1. Registration + config shape
# ---------------------------------------------------------------------------


def test_llmtr_is_registered_with_the_openai_exception_family():
    spec = get_provider("llmtr")
    assert spec.factory is LLMTRProvider
    assert spec.sdk_exception_refs == ("openai:OpenAIError",)
    # base_url is pinned through client_kwargs so a stored ``llmtr_proxy``
    # can still override it at call time (same contract as _compat.py).
    assert spec.client_kwargs["base_url"] == "https://llmtr.com/v1"


def test_llmtr_json_block_declares_the_gateway_contract():
    block = _llm_defaults()["providers"]["llmtr"]
    assert block["base_url"] == "https://llmtr.com/v1"
    assert block["routes_vendor_prefixed_models"] is True
    # ``openai`` needs no alias (LLMTR spells it the same) but must resolve.
    assert "openai" in _llm_defaults()["providers"]
    # LLMTR normalizes every vendor onto reasoning_effort.
    assert block["thinking_type"] == "effort"
    # It DOES publish a model list — the opposite of Sarvam.
    assert block.get("supports_model_listing", True) is True


def test_llmtr_vendor_aliases_all_point_at_real_provider_blocks():
    providers = _llm_defaults()["providers"]
    aliases = providers["llmtr"].get("vendor_aliases", {})
    assert aliases, "gateway routing without aliases silently no-ops for google/moonshot"
    for prefix, target in aliases.items():
        assert target in providers, (
            f"vendor_aliases maps {prefix!r} -> {target!r}, which is not a provider block; "
            "the routing branch would fall back to the gateway's generic shape"
        )


# ---------------------------------------------------------------------------
# 2. Open-world membership (vendor/model ids)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "anthropic/claude-sonnet-5",
        "openai/gpt-4o",
        "qwen/qwen3.8-max",
        "llmtr/trendyol-7b",
    ],
)
def test_vendor_prefixed_models_are_valid_for_the_gateway(model):
    """No LLMTR id contains "llmtr" except its own rows, so the cloud-style
    substring check would reject the entire catalogue."""
    assert is_model_valid_for_provider(model, "llmtr") is True


def test_llmtr_is_a_router_provider_for_registry_lookups():
    """Membership is what lets ``get_model_info`` strip the vendor prefix and
    recover the real context window from the router cache."""
    assert "llmtr" in _ROUTER_PROVIDERS
    assert "openrouter" in _ROUTER_PROVIDERS


def test_single_vendor_providers_are_not_router_providers():
    """The cross-provider fallback must stay gateway-only — otherwise one
    vendor's limits would answer for another's model."""
    for provider in ("openai", "anthropic", "deepseek", "groq", "mistral"):
        assert provider not in _ROUTER_PROVIDERS


# ---------------------------------------------------------------------------
# 3. Catalogue filtering
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def _fetch_with_catalogue(rows: List[Dict[str, Any]]) -> List[str]:
    """Run ``fetch_models`` against a stubbed catalogue."""
    import asyncio

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *args, **kwargs):
            return _Response({"object": "list", "data": rows})

    with patch("httpx.AsyncClient", return_value=_Client()):
        return asyncio.run(_provider().fetch_models("llmtr-test-key"))


def test_fetch_models_keeps_only_chat_capable_rows():
    models = _fetch_with_catalogue(
        [
            {"id": "anthropic/claude-sonnet-5", "supported_operations": ["CHAT_COMPLETIONS"]},
            {"id": "voyageai/voyage-3", "supported_operations": ["EMBEDDINGS"]},
            {"id": "recraft/recraft-v3", "supported_operations": ["IMAGES_GENERATIONS"]},
            {"id": "openai/gpt-5.6-sol", "supported_operations": ["RESPONSES"]},
            {"id": "some/reranker", "supported_operations": ["RERANK"]},
        ]
    )
    assert models == ["anthropic/claude-sonnet-5"]


def test_fetch_models_keeps_a_row_that_also_does_something_else():
    """Multi-modality is not disqualifying — only the absence of chat is."""
    models = _fetch_with_catalogue(
        [{"id": "vendor/multi", "supported_operations": ["EMBEDDINGS", "CHAT_COMPLETIONS"]}]
    )
    assert models == ["vendor/multi"]


def test_fetch_models_is_permissive_when_operations_are_absent():
    """A missing declaration must never silently hide a working model — the
    same convention the speech/translate capability configs follow."""
    models = _fetch_with_catalogue(
        [{"id": "vendor/undeclared"}, {"id": "vendor/empty", "supported_operations": []}]
    )
    assert models == ["vendor/empty", "vendor/undeclared"]


def test_responses_only_models_are_excluded_by_construction():
    """``RESPONSES`` must stay out of the accept-set: the gateway serves those
    rows only at /v1/responses, which this provider never posts to."""
    assert CHAT_OPERATIONS == frozenset({"CHAT_COMPLETIONS"})


# ---------------------------------------------------------------------------
# 4. Policy split — wire shape from the vendor, thinking from the gateway
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,max_completion_tokens,temperature_allowed",
    [
        # o-series: verified live to 400 on max_tokens + temperature.
        ("openai/o4-mini", True, False),
        ("openai/o3", True, False),
        # GPT-5 family: same reasoning-capable wire shape.
        ("openai/gpt-5-nano", True, False),
        ("openai/gpt-5.4", True, False),
        # Ordinary chat rows keep max_tokens + temperature.
        ("openai/gpt-4o", False, True),
        ("anthropic/claude-sonnet-5", False, True),
        ("qwen/qwen3.8-max", False, True),
        # The gateway's own self-hosted rows have no vendor block: generic.
        ("llmtr/trendyol-7b", False, True),
    ],
)
def test_wire_shape_is_resolved_against_the_routed_vendor(
    model, max_completion_tokens, temperature_allowed
):
    policy = _provider()._model_policy(model, None)
    assert policy["max_completion_tokens"] is max_completion_tokens
    assert policy["temperature_allowed"] is temperature_allowed


def test_gateway_never_takes_the_responses_api_path():
    """The Responses API is vendor-native. Posting /v1/responses to a gateway
    for a row its catalogue publishes as chat-completions-only would 404."""
    provider = _provider()
    for model in ("openai/o4-mini", "openai/gpt-5.4", "openai/gpt-4o"):
        assert provider._model_policy(model, None)["use_responses"] is False


def test_thinking_type_stays_the_gateways_normalized_effort():
    """LLMTR accepts ``reasoning_effort`` for Anthropic and Google rows that
    natively take token budgets. Adopting the vendor's native ``budget`` type
    would emit an ``extra_body`` the gateway silently drops."""
    provider = _provider()
    for model in (
        "anthropic/claude-sonnet-5",  # native type is "budget"
        "google/gemini-3.6-flash",  # native type is "budget"
        "openai/o4-mini",  # native type is "effort"
        "llmtr/gemma-4",  # no vendor block
    ):
        assert provider._model_policy(model, None)["thinking_type"] == "effort"


def test_moonshot_fixed_temperature_survives_the_alias():
    """``moonshot/`` is LLMTR's spelling of our ``kimi`` block, which pins
    temperature 0.6 for the K2 family. Proves vendor_aliases actually routes."""
    policy = _provider()._model_policy("moonshot/kimi-k2.5", None)
    assert policy["fixed_temperature"] == 0.6


def test_unaliased_vendor_falls_back_to_the_generic_gateway_shape():
    policy = _provider()._model_policy("thinkingmachines/whatever-v1", None)
    assert policy["max_completion_tokens"] is False
    assert policy["temperature_allowed"] is True


# ---------------------------------------------------------------------------
# 5. The routing branch must not perturb any existing provider
# ---------------------------------------------------------------------------


def test_direct_openai_provider_is_unaffected_by_the_gateway_branch():
    """The regression that matters most: ``_model_policy`` is shared by ten
    providers, and OpenAI still owns the Responses API + its native effort."""
    with patch("openai.AsyncOpenAI"):
        direct = OpenAIProvider("key", provider_name="openai")

    o_series = direct._model_policy("o4-mini", None)
    assert o_series["max_completion_tokens"] is True
    assert o_series["use_responses"] is True
    assert o_series["temperature_allowed"] is False
    assert o_series["thinking_type"] == "effort"

    plain = direct._model_policy("gpt-4o", None)
    assert plain["max_completion_tokens"] is False
    assert plain["use_responses"] is False
    assert plain["temperature_allowed"] is True
    assert plain["thinking_type"] == "none"


def test_only_declared_gateways_opt_into_vendor_routing():
    """Groq also uses owner-qualified ids (``openai/gpt-oss-120b``) but is a
    single vendor — routing its models to OpenAI's block would send
    ``max_completion_tokens`` to Groq."""
    providers = _llm_defaults()["providers"]
    routed = {
        name
        for name, cfg in providers.items()
        if cfg.get("routes_vendor_prefixed_models")
    }
    assert routed == {"llmtr"}

    with patch("openai.AsyncOpenAI"):
        groq = OpenAIProvider("key", provider_name="groq")
    policy = groq._model_policy("openai/gpt-oss-120b", None)
    assert policy["max_completion_tokens"] is False
    assert policy["temperature_allowed"] is True
    # Groq's own gpt-oss effort rule still applies.
    assert policy["thinking_type"] == "effort"


# ---------------------------------------------------------------------------
# 6. Credential probe cannot rely on the public listing
# ---------------------------------------------------------------------------


def test_llmtr_credential_overrides_the_fetch_models_probe():
    """``_LLMApiKey._probe`` accepts any key whose model list loads. LLMTR's
    list loads for *every* string, so the subclass must not inherit it."""
    from nodes.model._credentials import LLMTRCredential, _LLMApiKey

    assert LLMTRCredential._probe.__func__ is not _LLMApiKey._probe.__func__


def test_llmtr_probe_authenticates_before_listing():
    """Ordering is load-bearing: a rejected key must never come back with a
    populated dropdown next to the error."""
    import inspect

    from nodes.model._credentials import LLMTRCredential

    body = inspect.getsource(LLMTRCredential._probe)
    chat_at = body.index("unifier.chat")
    fetch_at = body.index("fetch_models")
    assert chat_at < fetch_at
    # The raw LLMError must reach classify_credential_error, which reads its
    # status code; the unifier's own translation would flatten it.
    assert "translate_errors=False" in body


# ---------------------------------------------------------------------------
# 7. Embeddings — the gateway's second wire surface
# ---------------------------------------------------------------------------
#
# LLMTR serves ``/v1/embeddings`` in the same OpenAI wire format as its chat
# route, so it reuses ``OpenAIEmbedder`` rather than gaining an adapter. The
# one thing that must not regress is the pinned base_url: without it an
# ``llmtr`` selection silently builds a client pointed at api.openai.com and
# sends the user's LLMTR key there.


def test_llmtr_is_a_selectable_embedding_provider():
    from services.memory.vector_store import (
        DEFAULT_EMBEDDING_MODELS,
        default_embedding_model,
    )

    assert "llmtr" in DEFAULT_EMBEDDING_MODELS
    # Default is a Turkey-hosted row: keeping data in-region is the reason to
    # choose this gateway, so the default must not be a foreign vendor.
    assert default_embedding_model("llmtr").startswith("llmtr/")


def test_llmtr_embedder_pins_the_gateway_endpoint():
    """The regression that would leak an LLMTR key to OpenAI."""
    from services.memory.vector_store import create_embedder

    embedder = create_embedder("llmtr", api_key="llmtr-test-key")
    assert "llmtr.com" in str(embedder._client.base_url)


def test_llmtr_embedder_honours_an_explicit_endpoint():
    from services.memory.vector_store import create_embedder

    embedder = create_embedder(
        "llmtr", api_key="llmtr-test-key", endpoint="https://self.hosted/v1"
    )
    assert "self.hosted" in str(embedder._client.base_url)


def test_openai_embedder_keeps_the_sdk_default_endpoint():
    """Pinning must be per-provider — plain OpenAI still resolves its own."""
    from services.memory.vector_store import create_embedder

    embedder = create_embedder("openai", api_key="sk-test")
    assert "openai.com" in str(embedder._client.base_url)


def test_llmtr_embeddings_require_a_key():
    """An empty key must fail loudly rather than build an unauthenticated
    client that 401s later inside a batch."""
    from services.memory.vector_store import (
        EmbedderUnavailableError,
        create_embedder,
    )

    with pytest.raises(EmbedderUnavailableError):
        create_embedder("llmtr", api_key="")


def test_embedding_generator_node_exposes_llmtr_with_a_key_field():
    """A provider the node can select but never receive a key for is dead."""
    from typing import get_args

    from nodes.document.embedding_generator import EmbeddingGeneratorParams

    providers = set(get_args(EmbeddingGeneratorParams.model_fields["provider"].annotation))
    assert "llmtr" in providers

    api_key_field = EmbeddingGeneratorParams.model_fields["api_key"]
    shown_for = api_key_field.json_schema_extra["displayOptions"]["show"]["provider"]
    assert "llmtr" in shown_for
