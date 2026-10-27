"""Thin wrapper around the Anthropic SDK: sends messages, returns plain data.

Prompts, tool definitions, tool dispatch and fallbacks are business logic and live in services.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ...config import Settings
from .errors import ClaudeUnavailable

TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass(frozen=True)
class ClaudeReply:
    stop_reason: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The reply's content blocks as dicts, so a tool loop can send them back as the assistant turn.
    assistant_content: list[dict] = field(default_factory=list)


def _default_sdk(api_key: str) -> Any:
    import anthropic  # imported lazily so the app starts without network config

    return anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)


def _block_to_dict(block: Any) -> dict:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return dict(vars(block))


class ClaudeClient:
    def __init__(self, settings: Settings, sdk_factory: Callable[[str], Any] = _default_sdk):
        self.settings = settings
        self._sdk_factory = sdk_factory

    @property
    def enabled(self) -> bool:
        return self.settings.claude_enabled

    @property
    def fast_model(self) -> str:
        return self.settings.claude_fast_model

    @property
    def smart_model(self) -> str:
        return self.settings.claude_smart_model

    def create_message(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int,
        tools: list[dict] | None = None,
    ) -> ClaudeReply:
        """Send one Messages API request. Raises ClaudeUnavailable if disabled or on any API failure."""
        if not self.enabled:
            raise ClaudeUnavailable("ANTHROPIC_API_KEY is not set.")
        request = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
        if tools:
            request["tools"] = tools
        try:
            response = self._sdk_factory(self.settings.anthropic_api_key).messages.create(**request)
        except Exception as e:  # noqa: BLE001 - SDK, network and auth errors all mean "use the fallback"
            raise ClaudeUnavailable(str(e)) from e

        blocks = list(response.content)
        return ClaudeReply(
            stop_reason=response.stop_reason or "",
            text="".join(b.text for b in blocks if getattr(b, "type", "") == "text").strip(),
            tool_calls=[
                ToolCall(id=b.id, name=b.name, input=dict(b.input))
                for b in blocks
                if getattr(b, "type", "") == "tool_use"
            ],
            assistant_content=[_block_to_dict(b) for b in blocks],
        )
