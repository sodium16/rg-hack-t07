"""HTTP POST with bounded retries and errors safe to show a user.

Both Azure clients need the same behaviour: a timeout, retries only on 429 and
5xx, and an error message that never contains a credential. Centralising it
means the retry rule is tested once.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_SNIPPET_LIMIT = 400
_MAX_RETRY_AFTER_S = 30.0
_KEY_PATTERN = re.compile(r"(?i)(ocp-apim-subscription-key|api-key)\s*[:=]\s*\S+")


@dataclass(frozen=True)
class RetryPolicy:
    """Three attempts, short exponential delay with jitter."""

    attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 4.0


class HttpError(RuntimeError):
    """A network call failed. The message is user-facing and key-free."""


class HttpStatusError(HttpError):
    """Azure answered with an error status."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _delay_seconds(attempt: int, policy: RetryPolicy) -> float:
    backoff = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
    return backoff * (0.5 + random.random() / 2)


def _retry_after(response: Any) -> float | None:
    """Honour a Retry-After header when Azure sends one (429s usually do)."""
    try:
        raw = response.headers.get("Retry-After")
    except Exception:  # pragma: no cover - a response without headers
        return None
    if raw is None:
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        return None
    return max(0.0, min(seconds, _MAX_RETRY_AFTER_S))


def _snippet(response: Any) -> str:
    try:
        text = str(response.text or "")
    except Exception:  # pragma: no cover - a response that cannot be read
        return "(no response body)"
    text = " ".join(text.split())[:_SNIPPET_LIMIT]
    return _KEY_PATTERN.sub(r"\1: [redacted]", text) or "(empty response body)"


def post(
    url: str,
    *,
    headers: dict[str, str],
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float,
    policy: RetryPolicy = RetryPolicy(),
    sleeper: Callable[[float], None] = time.sleep,
    session: Any | None = None,
) -> Any:
    """POST once, retrying 429/5xx and network failures up to ``attempts``.

    Non-retryable statuses raise immediately with a redacted body snippet so
    the caller can map them to a friendly message.
    """
    client = session or requests
    last_network_error: Exception | None = None

    for attempt in range(1, policy.attempts + 1):
        try:
            response = client.post(
                url,
                headers=headers,
                data=data,
                files=files,
                json=json_body,
                timeout=timeout,
            )
        except requests.RequestException as error:  # network-level failure
            last_network_error = error
            if attempt == policy.attempts:
                break
            sleeper(_delay_seconds(attempt, policy))
            continue

        status = int(getattr(response, "status_code", 0))
        if status < 400:
            return response
        if status not in RETRYABLE_STATUS or attempt == policy.attempts:
            raise HttpStatusError(
                f"Azure returned HTTP {status}: {_snippet(response)}",
                status_code=status,
            )
        sleeper(_retry_after(response) or _delay_seconds(attempt, policy))

    raise HttpError(
        f"Could not reach Azure after {policy.attempts} attempts. "
        "Check your internet connection and try again."
    ) from last_network_error
