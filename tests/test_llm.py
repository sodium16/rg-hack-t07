"""Offline tests for the Foundry chat client."""

import json

import pytest

from app.llm import (
    ContentFilterError,
    FoundryClient,
    LLMError,
    LLMResponseError,
)
from tests.conftest import FakeResponse, FakeSession


def make_client(session) -> FoundryClient:
    return FoundryClient(
        endpoint="https://example.openai.azure.com/",
        key="secret-key",
        deployment="chat",
        api_version="2024-10-21",
        session=session,
        sleeper=lambda _: None,
    )


def chat_payload(content: str, finish: str = "stop", usage: dict | None = None) -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": finish}
        ],
        "usage": usage or {"total_tokens": 42, "prompt_tokens": 20},
    }


def test_returns_parsed_json_and_usage():
    session = FakeSession([FakeResponse(200, chat_payload('{"ok": true}'))])
    result = make_client(session).complete_json("system", "user")

    assert result.data == {"ok": True}
    assert result.finish_reason == "stop"
    assert result.usage["total_tokens"] == 42

    call = session.calls[0]
    assert "deployments/chat/chat/completions" in call["url"]
    assert "api-version=2024-10-21" in call["url"]
    assert call["headers"]["api-key"] == "secret-key"
    assert call["json"]["response_format"] == {"type": "json_object"}


def test_project_endpoint_uses_the_v1_route():
    session = FakeSession([FakeResponse(200, chat_payload('{"ok": true}'))])
    FoundryClient(
        endpoint="https://res.services.ai.azure.com/api/projects/p11",
        key="secret-key",
        deployment="chat",
        api_version="2025-04-14",
        session=session,
        sleeper=lambda _: None,
    ).complete_json("s", "u")

    call = session.calls[0]
    assert call["url"] == (
        "https://res.services.ai.azure.com/api/projects/p11/openai/v1/chat/completions"
    )
    assert call["json"]["model"] == "chat"
    assert "api-version" not in call["url"]
    assert call["headers"]["Authorization"] == "Bearer secret-key"


def test_openai_v1_endpoint_uses_root_v1_route():
    session = FakeSession([FakeResponse(200, chat_payload('{"ok": true}'))])
    FoundryClient(
        endpoint="https://res.services.ai.azure.com/openai/v1/",
        key="secret-key",
        deployment="chat",
        api_version="2025-04-14",
        session=session,
        sleeper=lambda _: None,
    ).complete_json("s", "u")

    assert session.calls[0]["url"] == (
        "https://res.services.ai.azure.com/openai/v1/chat/completions"
    )
    assert session.calls[0]["json"]["model"] == "chat"


def test_parses_fenced_json():
    session = FakeSession([FakeResponse(200, chat_payload('```json\n{"a": 1}\n```'))])
    assert make_client(session).complete_json("s", "u").data == {"a": 1}


def test_content_filter_raises_typed_error():
    session = FakeSession([FakeResponse(200, chat_payload("", finish="content_filter"))])
    with pytest.raises(ContentFilterError, match="content filter"):
        make_client(session).complete_json("s", "u")


def test_invalid_json_is_repaired_once():
    session = FakeSession(
        [FakeResponse(200, chat_payload("not json at all")), FakeResponse(200, chat_payload('{"fixed": true}'))]
    )
    result = make_client(session).complete_json("s", "u")
    assert result.data == {"fixed": True}
    assert len(session.calls) == 2
    repair_messages = session.calls[1]["json"]["messages"]
    assert [message["role"] for message in repair_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]


def test_invalid_json_twice_raises_response_error():
    session = FakeSession(
        [FakeResponse(200, chat_payload("nope")), FakeResponse(200, chat_payload("still nope"))]
    )
    with pytest.raises(LLMResponseError, match="valid JSON"):
        make_client(session).complete_json("s", "u")


def test_max_tokens_is_retried_as_max_completion_tokens():
    error_text = '{"error":{"message":"Use max_completion_tokens instead of max_tokens"}}'
    session = FakeSession(
        [FakeResponse(400, text=error_text), FakeResponse(200, chat_payload('{"ok": true}'))]
    )
    result = make_client(session).complete_json("s", "u")

    assert result.data == {"ok": True}
    retried_body = session.calls[1]["json"]
    assert "max_completion_tokens" in retried_body
    assert "max_tokens" not in retried_body


def test_unknown_deployment_is_explained():
    session = FakeSession([FakeResponse(404, text="deployment not found")])
    with pytest.raises(LLMError, match="AZURE_FOUNDRY_DEPLOYMENT"):
        make_client(session).complete_json("s", "u")


def test_key_is_not_echoed_in_errors():
    body = json.dumps({"error": "bad api-key: secret-key"})
    session = FakeSession([FakeResponse(401, text=body)])
    with pytest.raises(LLMError) as error:
        make_client(session).complete_json("s", "u")
    assert "secret-key" not in str(error.value)
