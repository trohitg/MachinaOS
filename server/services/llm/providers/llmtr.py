"""LLMTR provider — Turkish multi-vendor gateway, OpenAI-compatible.

LLMTR (llmtr.com) is a router, not a single-vendor endpoint: one key
fronts ~230 catalogue rows across OpenAI / Anthropic / Google / Qwen /
DeepSeek / Mistral / xAI plus Turkey-hosted models of its own, and every
id is ``vendor/model``. Wire-wise it is plain OpenAI at
``https://llmtr.com/v1``, so it inherits :class:`OpenAIProvider` whole
and overrides exactly one method.

**Why this is a dedicated module rather than one more name in**
``_COMPAT_PROVIDERS``: the compat path uses ``OpenAIProvider.fetch_models``,
which returns ``sorted(m.id for m in models.list().data)`` — every row.
LLMTR's catalogue is mixed-modality: of 229 rows only 165 accept
``/v1/chat/completions``; the rest are embeddings (voyageai), image
(recraft), video, rerank, audio and Responses-only models. Serving that
list unfiltered puts ``voyageai/voyage-3`` in the chat-model dropdown,
where picking it fails at request time with an opaque 404 rather than at
selection time. LLMTR publishes ``supported_operations`` per row, so the
filter is a documented field read, not a heuristic.

This is the same shape :class:`OpenRouterProvider` already uses — the
other gateway here, which likewise subclasses ``OpenAIProvider`` purely
to reshape its model list.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.logging import get_logger
from services.llm.providers.openai import OpenAIProvider

logger = get_logger(__name__)

#: Wire default. A stored ``llmtr_proxy`` credential still wins — see
#: ``__init__`` — so a self-hosted or regional LLMTR deployment needs no
#: code change.
LLMTR_BASE_URL = "https://llmtr.com/v1"

#: Catalogue rows whose ``supported_operations`` include one of these are
#: usable by a chat-model node. ``CHAT_COMPLETIONS`` is the endpoint this
#: provider actually posts to. ``RESPONSES`` rows (openai/gpt-5.6-*,
#: xai/grok-4.5, ...) are deliberately EXCLUDED: LLMTR exposes them only
#: at ``/v1/responses``, and ``OpenAIProvider`` picks the Responses API
#: from its own per-model policy against *OpenAI's* naming, which cannot
#: know that a given id is Responses-only on a third-party gateway.
#: Listing them would surface models that 404 on every call.
CHAT_OPERATIONS = frozenset({"CHAT_COMPLETIONS"})


class LLMTRProvider(OpenAIProvider):
    provider_name = "llmtr"

    def __init__(
        self,
        api_key: str,
        *,
        proxy_url: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_name: Optional[str] = None,
        max_retries: int = 2,
    ):
        # Resolve the effective endpoint ourselves so ``fetch_models`` can
        # reuse it. Deliberately NOT the ``proxy_url`` branch in
        # ``OpenAIProvider.__init__``: that one replaces the api_key with
        # the local-server placeholder ("ollama"), which is right for an
        # unauthenticated Ollama/LM Studio box and wrong for LLMTR — a
        # self-hosted LLMTR still authenticates with a real llmtr- key.
        self._base_url = (proxy_url or base_url or LLMTR_BASE_URL).rstrip("/")
        super().__init__(
            api_key,
            base_url=self._base_url,
            provider_name=provider_name or type(self).provider_name,
            max_retries=max_retries,
        )

    async def fetch_models(self, api_key: str) -> List[str]:
        """Return only the ids that accept ``/v1/chat/completions``.

        Read over httpx rather than ``self._client.models.list()``
        because the discriminating field (``supported_operations``) is
        outside the OpenAI model schema; the SDK keeps unknown keys in
        ``model_extra``, but depending on that is depending on an
        implementation detail of a third-party pydantic config.

        ``GET /v1/models`` on LLMTR is public — it answers 200 with no
        key at all. The Authorization header is still sent so a
        future/self-hosted deployment that does gate the route works
        unchanged, but a caller must NOT read a successful return here as
        proof the key is valid. Credential validation lives in
        ``LLMTRCredential._probe`` (a 1-token completion) precisely
        because this route cannot perform it.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()

        models: List[str] = []
        skipped = 0
        for raw in data.get("data", []) or []:
            model_id = raw.get("id") or ""
            if not model_id:
                continue
            operations = raw.get("supported_operations") or []
            # Absent/empty ``supported_operations`` is treated as chat —
            # permissive, matching the speech/translate capability
            # convention: a missing declaration must never silently hide a
            # working model.
            if operations and not (CHAT_OPERATIONS & set(operations)):
                skipped += 1
                continue
            models.append(model_id)

        if skipped:
            logger.debug(
                "llmtr catalogue filtered to chat-capable rows",
                kept=len(models),
                skipped=skipped,
            )
        return sorted(models)


# ---------------------------------------------------------------------------
# Plugin self-registration
# ---------------------------------------------------------------------------
# LLMTR rides the OpenAI Python SDK against its own base_url, so its typed
# exceptions are ``openai.OpenAIError`` subclasses — same lazy exception
# ref as the openai / openrouter providers. ``base_url`` is pinned through
# ``client_kwargs`` the way ``_compat.py`` pins the compat endpoints, so a
# stored ``llmtr_proxy`` still overrides it at call time.

from services.llm.registry import ProviderSpec, register_provider  # noqa: E402

_CLIENT_KWARGS: Dict[str, Any] = {"base_url": LLMTR_BASE_URL}

register_provider(
    ProviderSpec(
        name="llmtr",
        factory=LLMTRProvider,
        sdk_exception_refs=("openai:OpenAIError",),
        client_kwargs=_CLIENT_KWARGS,
    )
)
