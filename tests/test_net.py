"""Offline tests for the shared HTTP retry wrapper."""

import requests
import pytest

from app import net
from tests.conftest import FakeResponse, FakeSession


def test_retries_retryable_status_then_succeeds():
    session = FakeSession([FakeResponse(503, {"error": "busy"}), FakeResponse(200, {"ok": True})])
    delays: list[float] = []
    response = net.post(
        "https://example.test", headers={}, timeout=5, sleeper=delays.append, session=session
    )
    assert response.status_code == 200
    assert len(session.calls) == 2
    assert len(delays) == 1


def test_gives_up_after_three_attempts():
    session = FakeSession([FakeResponse(429, text="slow down") for _ in range(3)])
    with pytest.raises(net.HttpStatusError) as error:
        net.post(
            "https://example.test",
            headers={},
            timeout=5,
            sleeper=lambda _: None,
            session=session,
        )
    assert error.value.status_code == 429
    assert len(session.calls) == 3


def test_retry_after_header_sets_the_delay():
    session = FakeSession(
        [
            FakeResponse(429, text="busy", headers={"Retry-After": "7"}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    delays: list[float] = []
    net.post(
        "https://example.test", headers={}, timeout=5, sleeper=delays.append, session=session
    )
    assert delays == [7.0]


def test_retry_after_is_capped():
    session = FakeSession(
        [
            FakeResponse(429, text="busy", headers={"Retry-After": "3600"}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    delays: list[float] = []
    net.post(
        "https://example.test", headers={}, timeout=5, sleeper=delays.append, session=session
    )
    assert delays == [30.0]


def test_non_retryable_status_raises_immediately():
    session = FakeSession([FakeResponse(400, text="bad request")])
    with pytest.raises(net.HttpStatusError) as error:
        net.post(
            "https://example.test",
            headers={},
            timeout=5,
            sleeper=lambda _: None,
            session=session,
        )
    assert error.value.status_code == 400
    assert len(session.calls) == 1


def test_error_body_redacts_api_key():
    session = FakeSession([FakeResponse(401, text='{"error":"bad api-key: sk-secret-value"}')])
    with pytest.raises(net.HttpStatusError) as error:
        net.post(
            "https://example.test",
            headers={},
            timeout=5,
            sleeper=lambda _: None,
            session=session,
        )
    assert "sk-secret-value" not in str(error.value)
    assert "[redacted]" in str(error.value)


def test_network_failure_becomes_friendly_error_after_retries():
    calls: list[int] = []

    class Broken:
        def post(self, *args, **kwargs):
            calls.append(1)
            raise requests.ConnectionError("no route to host")

    with pytest.raises(net.HttpError, match="Could not reach Azure"):
        net.post(
            "https://example.test",
            headers={},
            timeout=5,
            sleeper=lambda _: None,
            session=Broken(),
        )
    assert len(calls) == 3
