import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "chat/completions"
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
CODE_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


@dataclass(frozen=True)
class LlmClientConfig:
    base_url: str
    api_key: SecretStr
    model: str
    timeout_s: float
    max_retries: int
    max_output_tokens: int
    max_response_bytes: int
    temperature: float


class LlmError(Exception):
    """The LLM call failed or returned something unusable; callers use RULES."""


class LlmClient(Protocol):
    """Port to a chat LLM that answers with one JSON object."""

    @property
    def model(self) -> str:
        """Name of the model, reported in the response."""
        ...

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        """Send the prompts and return the JSON object the model answered.

        Raises LlmError on any failure (network, timeout, HTTP error, oversized
        or malformed answer).
        """
        ...


class OpenAiCompatibleClient:
    """Adapter for any server with the OpenAI `/chat/completions` endpoint."""

    def __init__(
        self,
        config: LlmClientConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._url = config.base_url.rstrip("/") + "/" + CHAT_COMPLETIONS_PATH
        self._transport = transport

    @property
    def model(self) -> str:
        return self._config.model

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_output_tokens,
        }
        last_error: LlmError | None = None
        for _attempt in range(self._config.max_retries + 1):
            try:
                return self._parse(self._post(payload))
            except _RetryableError as error:
                last_error = LlmError(str(error))
                logger.warning("LLM call failed, may retry: %s", error)
        raise last_error or LlmError("LLM call failed")

    def _post(self, payload: dict[str, Any]) -> bytes:
        headers = {"Authorization": f"Bearer {self._config.api_key.get_secret_value()}"}
        try:
            with (
                httpx.Client(
                    timeout=self._config.timeout_s, transport=self._transport
                ) as client,
                client.stream(
                    "POST", self._url, json=payload, headers=headers
                ) as response,
            ):
                status = response.status_code
                if status == HTTP_TOO_MANY_REQUESTS:
                    raise LlmError("LLM rate limited (429)")
                if status >= HTTP_SERVER_ERROR_MIN:
                    raise _RetryableError(f"LLM server error ({status})")
                if status >= httpx.codes.BAD_REQUEST:
                    raise LlmError(f"LLM rejected the request ({status})")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self._config.max_response_bytes:
                        raise LlmError("LLM response exceeds the size limit")
                return bytes(body)
        except httpx.TimeoutException as error:
            raise _RetryableError("LLM timeout") from error
        except httpx.TransportError as error:
            raise _RetryableError(
                f"LLM transport error: {type(error).__name__}"
            ) from error

    @staticmethod
    def _parse(body: bytes) -> dict[str, Any]:
        try:
            envelope = json.loads(body)
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("content is not text")
            fenced = CODE_FENCE.match(content.strip())
            parsed = json.loads(fenced.group(1) if fenced else content)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LlmError("LLM returned an unusable answer") from error
        if not isinstance(parsed, dict):
            raise LlmError("LLM answer is not a JSON object")
        return parsed


class _RetryableError(LlmError):
    """Timeouts, connection problems and 5xx answers are worth another try."""
