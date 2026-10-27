from types import SimpleNamespace as NS

import anthropic
import pytest
from anthropic.types import TextBlock, ToolUseBlock

from app.config import Settings
from app.integrations.anthropic import ClaudeClient, ClaudeUnavailable, ToolCall
from app.integrations.anthropic.client import _default_sdk


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{"anthropic_api_key": "sk-ant-test", **overrides})


class FakeSdk:
    def __init__(self, response=None, fail_with: Exception | None = None):
        self.requests: list[dict] = []
        self.response, self.fail_with = response, fail_with
        self.messages = NS(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        if self.fail_with:
            raise self.fail_with
        return self.response


def client_with(sdk: FakeSdk, **overrides) -> ClaudeClient:
    return ClaudeClient(settings(**overrides), sdk_factory=lambda key: sdk)


def test_default_sdk_builds_anthropic_client_with_timeout():
    sdk = _default_sdk("sk-ant-test")
    assert isinstance(sdk, anthropic.Anthropic)
    assert sdk.timeout == 60


def test_disabled_client_raises_without_calling_api():
    sdk = FakeSdk()
    client = client_with(sdk, anthropic_api_key="sk-ant-xxx")
    assert not client.enabled
    with pytest.raises(ClaudeUnavailable):
        client.create_message(model="m", system="s", messages=[], max_tokens=10)
    assert sdk.requests == []


def test_text_reply_is_converted_to_plain_data():
    response = NS(stop_reason="end_turn", content=[TextBlock(type="text", text="  Hello "), TextBlock(type="text", text="there")])
    sdk = FakeSdk(response)
    reply = client_with(sdk).create_message(model="m", system="sys", messages=[{"role": "user", "content": "hi"}], max_tokens=50)

    assert reply.stop_reason == "end_turn"
    assert reply.text == "Hello there"
    assert reply.tool_calls == []
    assert reply.assistant_content == [{"type": "text", "text": "  Hello "}, {"type": "text", "text": "there"}]
    assert "tools" not in sdk.requests[0]
    assert sdk.requests[0]["system"] == "sys" and sdk.requests[0]["max_tokens"] == 50


def test_tool_use_reply_exposes_tool_calls_and_echoable_content():
    block = ToolUseBlock(type="tool_use", id="tu_1", name="get_period_summary", input={"start": "2026-01-01"})
    sdk = FakeSdk(NS(stop_reason="tool_use", content=[block]))
    tools = [{"name": "get_period_summary", "input_schema": {"type": "object"}}]
    reply = client_with(sdk).create_message(model="m", system="s", messages=[], max_tokens=10, tools=tools)

    assert reply.tool_calls == [ToolCall(id="tu_1", name="get_period_summary", input={"start": "2026-01-01"})]
    assert reply.assistant_content == [{"type": "tool_use", "id": "tu_1", "name": "get_period_summary", "input": {"start": "2026-01-01"}}]
    assert sdk.requests[0]["tools"] == tools


def test_api_errors_become_claude_unavailable():
    client = client_with(FakeSdk(fail_with=RuntimeError("overloaded")))
    with pytest.raises(ClaudeUnavailable, match="overloaded"):
        client.create_message(model="m", system="s", messages=[], max_tokens=10)


def test_models_come_from_settings():
    client = client_with(FakeSdk(), claude_fast_model="fast-x", claude_smart_model="smart-y")
    assert (client.fast_model, client.smart_model) == ("fast-x", "smart-y")
