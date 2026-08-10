from typing import Optional

from pydantic import Field

from .._base import ChatModelBase, ChatModelParams

from .._credentials import LLMTRCredential


class LLMTRChatModelParams(ChatModelParams):
    frequency_penalty: Optional[float] = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
    )
    presence_penalty: Optional[float] = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
    )


class LLMTRChatModelNode(ChatModelBase):
    """LLMTR gateway chat model.

    Same shape as the OpenRouter node — a gateway, so the params surface
    stays deliberately generic. No thinking/reasoning fields are declared
    even though many routed models support reasoning: the effective
    parameter set depends on which vendor the selected ``vendor/model`` id
    lands on, and a field the chosen model does not accept is a 400 at
    request time rather than a disabled control. The inherited
    ``thinking_enabled`` / ``reasoning_effort`` from
    :class:`ChatModelParams` remain available for models that do take them.
    """

    type = "llmtrChatModel"
    display_name = "LLMTR"
    subtitle = "Chat Model"
    group = ("model",)
    description = (
        "LLMTR gateway - one Turkish-billed key for OpenAI, Claude, Gemini, "
        "Qwen, DeepSeek and Turkey-hosted models"
    )

    credentials = (LLMTRCredential,)
    Params = LLMTRChatModelParams
