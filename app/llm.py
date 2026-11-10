"""Foundry chat client: JSON output, bounded retries, friendly failures.

The model is a grounding source only — it returns quotes and text, never
timestamps. This module keeps the transport concerns (auth, retries, JSON mode,
content-filter errors) out of the prompts and pipelines.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app import net
from app.config import load_settings, require_azure_env


class LLMError(RuntimeError):
    """A chat call failed. The message is safe to show the student."""


class ContentFilterError(LLMError):
    """The deployment's content filter blocked the response."""


class LLMResponseError(LLMError):
    """The model answered with something unusable (empty or non-JSON)."""


class _InvalidJSON(Exception):
    def __init__(self, content: str) -> None:
        super().__init__("invalid JSON")
        self.content = content


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    finish_reason: str | None
    usage: dict[str, Any]


class ChatModel(Protocol):
    """What the notes and Q&A pipelines need from a model."""

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1600,
        temperature: float = 0.0,
    ) -> LLMResult: ...


def _chat_target(endpoint: str, deployment: str, api_version: str) -> tuple[str, bool]:
    """Return (url, uses_v1_api) for the endpoint shape in the environment.

    Foundry project resources expose the OpenAI v1 API under
    ``/openai/v1`` (either on the project URL or on the resource root), where
    the deployment is named by ``model`` in the body. Classic Azure OpenAI
    resources still use ``/openai/deployments/<name>`` with an api-version.
    """
    base = endpoint.rstrip("/")
    if base.endswith("/openai/v1"):
        return f"{base}/chat/completions", True
    if "/api/projects/" in base:
        return f"{base}/openai/v1/chat/completions", True
    if base.endswith("/openai"):
        return f"{base}/v1/chat/completions", True
    if ".services.ai.azure.com" in base:
        return f"{base}/openai/v1/chat/completions", True
    return (
        f"{base}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={api_version}",
        False,
    )


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise _InvalidJSON(content)
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise _InvalidJSON(content) from error
    if not isinstance(data, dict):
        raise _InvalidJSON(content)
    return data


class FoundryClient:
    """Azure OpenAI-compatible chat deployment with JSON mode."""

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        deployment: str,
        api_version: str,
        session: Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
        policy: net.RetryPolicy = net.RetryPolicy(),
    ) -> None:
        self._url, self._is_v1 = _chat_target(endpoint, deployment, api_version)
        self._key = key
        self._deployment = deployment
        self._session = session
        self._sleeper = sleeper
        self._timeout = timeout
        self._policy = policy

    @classmethod
    def from_env(cls) -> "FoundryClient":
        values = require_azure_env()
        return cls(
            endpoint=values["AZURE_FOUNDRY_ENDPOINT"],
            key=values["AZURE_FOUNDRY_KEY"],
            deployment=values["AZURE_FOUNDRY_DEPLOYMENT"],
            api_version=values["AZURE_FOUNDRY_API_VERSION"],
        )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResult:
        config = load_settings()
        limit = max_tokens or config.llm_max_tokens
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": limit,
            "response_format": {"type": "json_object"},
        }
        if self._is_v1:
            body["model"] = self._deployment

        payload = self._post_mapped(body)
        try:
            return self._to_result(payload)
        except _InvalidJSON as invalid:
            # One repair attempt: show the model its own answer and ask again.
            repair_body: dict[str, Any] = {
                **body,
                "messages": messages
                + [
                    {"role": "assistant", "content": invalid.content},
                    {
                        "role": "user",
                        "content": "Return only valid JSON matching the requested schema, "
                        "with no markdown fences and no extra text.",
                    },
                ],
            }
            repaired = self._post_mapped(repair_body)
            try:
                return self._to_result(repaired)
            except _InvalidJSON as error:
                raise LLMResponseError(
                    "The model did not return valid JSON. Try again."
                ) from error

    def _post_mapped(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "api-key": self._key}
        if self._is_v1:
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            response = net.post(
                self._url,
                headers=headers,
                json_body=body,
                timeout=self._timeout,
                policy=self._policy,
                sleeper=self._sleeper,
                session=self._session,
            )
        except net.HttpStatusError as error:
            # Newer deployments reject max_tokens in favour of max_completion_tokens.
            if error.status_code == 400 and "max_completion_tokens" in str(error):
                adapted = dict(body)
                limit = adapted.pop("max_tokens", None)
                if limit is not None:
                    adapted["max_completion_tokens"] = limit
                try:
                    response = net.post(
                        self._url,
                        headers=headers,
                        json_body=adapted,
                        timeout=self._timeout,
                        policy=self._policy,
                        sleeper=self._sleeper,
                        session=self._session,
                    )
                except net.HttpStatusError as retry_error:
                    raise self._map_status(retry_error) from retry_error
            else:
                raise self._map_status(error) from error
        except net.HttpError as error:
            raise LLMError(str(error)) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise LLMResponseError("Foundry returned a response that was not JSON.") from error
        if not isinstance(payload, dict):
            raise LLMResponseError("Foundry returned an unexpected response.")
        return payload

    @staticmethod
    def _map_status(error: net.HttpStatusError) -> LLMError:
        if error.status_code in {401, 403}:
            return LLMError(
                "Foundry rejected the credentials. Check AZURE_FOUNDRY_ENDPOINT "
                "and AZURE_FOUNDRY_KEY."
            )
        if error.status_code == 404:
            return LLMError(
                "Foundry could not find that deployment. AZURE_FOUNDRY_DEPLOYMENT "
                "must be the deployment name, not the model name."
            )
        if error.status_code == 429:
            return LLMError("The model deployment is rate-limited. Wait a moment and try again.")
        return LLMError(f"Foundry call failed (HTTP {error.status_code}). Try again shortly.")

    @staticmethod
    def _to_result(payload: dict[str, Any]) -> LLMResult:
        choices = payload.get("choices") or []
        if not choices:
            raise LLMResponseError("The model returned no choices. Try again.")
        choice = choices[0] or {}
        finish_reason = choice.get("finish_reason")
        if finish_reason == "content_filter":
            raise ContentFilterError(
                "The content filter blocked this response, so it was not shown. "
                "Rephrase the question or use a different clip."
            )
        content = str((choice.get("message") or {}).get("content") or "").strip()
        if not content:
            raise LLMResponseError("The model returned an empty response. Try again.")
        return LLMResult(
            data=_parse_json_content(content),
            finish_reason=finish_reason,
            usage=payload.get("usage") or {},
        )
