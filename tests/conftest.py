"""Shared test doubles: no test in this suite touches Azure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_sample.json"


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.headers = headers or {}

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class FakeSession:
    """Returns queued responses and records every call."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected HTTP call to {url}")
        return self.responses.pop(0)


class ScriptedModel:
    """A chat model double: each call returns the next queued result."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> Any:
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, **kwargs}
        )
        if not self.results:
            raise AssertionError("unexpected model call")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture()
def transcript_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def speech_payload() -> dict[str, Any]:
    """A trimmed fast-transcription response shaped like the real thing."""
    return {
        "durationMilliseconds": 12000,
        "phrases": [
            {
                "offsetMilliseconds": 0,
                "durationMilliseconds": 4000,
                "text": "Gradient descent updates the weights.",
                "confidence": 0.94,
                "locale": "en-US",
                "words": [
                    {"text": "Gradient", "offsetMilliseconds": 0, "durationMilliseconds": 500},
                    {"text": "descent", "offsetMilliseconds": 500, "durationMilliseconds": 500},
                    {"text": "updates", "offsetMilliseconds": 1000, "durationMilliseconds": 500},
                    {"text": "the", "offsetMilliseconds": 1500, "durationMilliseconds": 200},
                    {"text": "weights", "offsetMilliseconds": 1700, "durationMilliseconds": 600},
                ],
            },
            {
                "offsetMilliseconds": 4000,
                "durationMilliseconds": 3000,
                "text": "The learning rate controls the step size.",
                "confidence": 0.88,
                "locale": "en-US",
            },
        ],
    }
