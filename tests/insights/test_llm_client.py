import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from caudal_ia.config import Settings
from caudal_ia.insights.llm import LlmClientConfig, LlmError, OpenAiCompatibleClient
from caudal_ia.routes.insights import build_llm_client

FAKE_KEY = "fake-key-for-tests"
MAX_OUTPUT_TOKENS = 100
ATTEMPTS_WITH_TWO_RETRIES = 3


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    retries: int = 1,
    max_bytes: int = 65536,
) -> OpenAiCompatibleClient:
    return OpenAiCompatibleClient(
        LlmClientConfig(
            base_url="https://llm.example.test/v1beta/openai/",
            api_key=SecretStr(FAKE_KEY),
            model="m",
            timeout_s=1.0,
            max_retries=retries,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_response_bytes=max_bytes,
            temperature=0.0,
        ),
        transport=httpx.MockTransport(handler),
    )


def chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_sends_openai_request_and_parses_json() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return chat('{"answer": "ok"}')

    assert make_client(handler).complete_json("sys", "usr") == {"answer": "ok"}
    request = seen[0]
    assert str(request.url) == "https://llm.example.test/v1beta/openai/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    payload = json.loads(request.content)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == MAX_OUTPUT_TOKENS
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]


def test_accepts_json_inside_code_fence() -> None:
    client = make_client(lambda _: chat('```json\n{"a": 1}\n```'))
    assert client.complete_json("s", "u") == {"a": 1}


@pytest.mark.parametrize("content", ["not json", "[1, 2]", ""])
def test_invalid_content_raises(content: str) -> None:
    with pytest.raises(LlmError):
        make_client(lambda _: chat(content)).complete_json("s", "u")


def test_429_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    with pytest.raises(LlmError):
        make_client(handler, retries=3).complete_json("s", "u")
    assert calls == 1


def test_timeout_is_retried_then_raises() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LlmError):
        make_client(handler, retries=2).complete_json("s", "u")
    assert calls == ATTEMPTS_WITH_TWO_RETRIES


def test_server_error_then_success() -> None:
    answers = iter([httpx.Response(503), chat('{"ok": true}')])
    client = make_client(lambda _: next(answers))
    assert client.complete_json("s", "u") == {"ok": True}


def test_oversized_response_raises() -> None:
    client = make_client(lambda _: chat('{"a": "' + "x" * 500 + '"}'), max_bytes=100)
    with pytest.raises(LlmError):
        client.complete_json("s", "u")


def make_settings(api_key: str | None) -> Settings:
    return Settings(
        ia_service_token=SecretStr("t" * 40),
        llm_api_key=SecretStr(api_key) if api_key else None,
        _env_file=None,
    )


def test_no_api_key_builds_no_client() -> None:
    assert build_llm_client(make_settings(None)) is None


def test_api_key_builds_the_openai_compatible_client() -> None:
    client = build_llm_client(make_settings(FAKE_KEY))
    assert isinstance(client, OpenAiCompatibleClient)
    assert client.model
