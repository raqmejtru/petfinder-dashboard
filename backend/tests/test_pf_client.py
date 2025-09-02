# backend/tests/test_pf_client.py
from __future__ import annotations

import time as _time
from typing import Any
from collections.abc import Iterator

import pytest
import requests
import responses

from backend.app.pf_client import (
    PetfinderClient,
    PetfinderAuthError,
    BASE_URL,
)

# ---------- helpers ----------


def _token_json(token: str = "tok", expires_in: int = 3600) -> dict[str, Any]:
    return {"token_type": "Bearer", "expires_in": expires_in, "access_token": token}


def _animals_page(ids: Iterator[int] | list[int], current: int, total: int) -> dict[str, Any]:
    return {
        "animals": [{"id": i} for i in ids],
        "pagination": {"current_page": current, "total_pages": total},
    }


# ---------- fixtures ----------


@pytest.fixture
def creds_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PF_CLIENT_ID", "id")
    monkeypatch.setenv("PF_CLIENT_SECRET", "secret")


# ---------- tests ----------


def test_missing_credentials_raises() -> None:
    """Raise PetfinderAuthError when no client ID/secret provided."""
    with pytest.raises(PetfinderAuthError):
        PetfinderClient(client_id=None, client_secret=None)


@responses.activate
def test_fetch_token_and_reuse(creds_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch token once, reuse if >60s remain, refresh if <60s remain."""

    # Freeze time to test expiry logic
    t0: float = 1_000_000.0
    now = t0
    monkeypatch.setattr(_time, "time", lambda: now)

    # 1) initial token
    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("A", expires_in=3600),
        status=200,
    )
    # a GET that will be called multiple times
    responses.add(
        responses.GET,
        f"{BASE_URL}/types",
        json={"types": [{"name": "Cat"}]},
        status=200,
    )
    responses.add(  # add a second GET response for the second call below
        responses.GET,
        f"{BASE_URL}/types",
        json={"types": [{"name": "Cat"}]},
        status=200,
    )

    c = PetfinderClient()
    out = c.get_types()
    assert out["types"][0]["name"] == "Cat"
    assert len([r for r in responses.calls if r.request.method == "POST"]) == 1

    # a) Reuse while > 60s remain:
    #    Move to 90s before expiry => should NOT refresh
    now = t0 + 3600 - 90
    monkeypatch.setattr(_time, "time", lambda: now)
    _ = c.get_types()
    assert len([r for r in responses.calls if r.request.method == "POST"]) == 1  # still 1

    # b) Refresh when < 60s remain:
    #    Move to 30s before expiry => SHOULD refresh
    responses.add(  # token refresh
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("B", expires_in=3600),
        status=200,
    )
    responses.add(  # GET after refresh
        responses.GET,
        f"{BASE_URL}/types",
        json={"types": [{"name": "Cat"}]},
        status=200,
    )
    now = t0 + 3600 - 30
    monkeypatch.setattr(_time, "time", lambda: now)
    _ = c.get_types()
    assert len([r for r in responses.calls if r.request.method == "POST"]) == 2  # refreshed


@responses.activate
def test_token_refresh_on_expiry(creds_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force token refresh when expiry threshold is passed."""

    t0: float = 1_000_000.0
    now: float = t0
    monkeypatch.setattr(_time, "time", lambda: now)

    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("A", expires_in=60),
        status=200,
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("B", expires_in=3600),
        status=200,
    )
    responses.add(responses.GET, f"{BASE_URL}/types", json={"ok": True}, status=200)
    responses.add(responses.GET, f"{BASE_URL}/types", json={"ok": True}, status=200)

    c = PetfinderClient()
    _ = c.get_types()  # uses token A (trigger API call, exercise token logic)
    # advance time beyond expiry - 60 buffer => force refresh
    now = t0 + 61
    monkeypatch.setattr(_time, "time", lambda: now)
    _ = c.get_types()  # should fetch token B (trigger API call, exercise token logic)

    posts = [r for r in responses.calls if r.request.method == "POST"]
    assert len(posts) == 2, "should have fetched token twice"


@responses.activate
def test_401_triggers_single_refresh(creds_env: None) -> None:
    """Retry once with a new token after a 401 Unauthorized response."""

    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("A"),
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/types",
        status=401,
        json={"error": "expired"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("B"),
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/types",
        status=200,
        json={"types": []},
    )

    c = PetfinderClient()
    out = c.get_types()
    assert "types" in out
    assert len([r for r in responses.calls if r.request.method == "POST"]) == 2


@responses.activate
def test_headers_include_bearer_token(creds_env: None) -> None:
    """Include Authorization header with Bearer token in requests."""

    responses.add(
        responses.POST,
        f"{BASE_URL}/oauth2/token",
        json=_token_json("SECRET"),
        status=200,
    )

    def _assert_auth(request: Any) -> tuple[int, dict[str, str], str]:
        assert request.headers.get("Authorization") == "Bearer SECRET"
        return (200, {}, '{"ok": true}')

    responses.add_callback(
        responses.GET,
        f"{BASE_URL}/types",
        callback=_assert_auth,
        content_type="application/json",
    )
    c = PetfinderClient()
    _ = c.get_types()  # assertions inside callback


@responses.activate
def test_get_types_passthrough(creds_env: None) -> None:
    """Return /types response JSON as-is."""

    responses.add(responses.POST, f"{BASE_URL}/oauth2/token", json=_token_json(), status=200)
    responses.add(responses.GET, f"{BASE_URL}/types", json={"types": [{"name": "Dog"}]}, status=200)
    c = PetfinderClient()
    out = c.get_types()
    assert out["types"][0]["name"] == "Dog"


@responses.activate
def test_iter_animals_paginates(creds_env: None) -> None:
    """Iterate across multiple pages of animals until pagination ends."""

    responses.add(responses.POST, f"{BASE_URL}/oauth2/token", json=_token_json(), status=200)
    responses.add(
        responses.GET, f"{BASE_URL}/animals", json=_animals_page([1, 2], 1, 2), status=200
    )
    responses.add(responses.GET, f"{BASE_URL}/animals", json=_animals_page([3], 2, 2), status=200)

    c = PetfinderClient()
    out = list(c.iter_animals(type="cat", limit=50))
    assert [a["id"] for a in out] == [1, 2, 3]


@responses.activate
def test_iter_animals_empty_and_missing_keys(creds_env: None) -> None:
    """Handle missing 'animals' or 'pagination' keys gracefully."""

    responses.add(responses.POST, f"{BASE_URL}/oauth2/token", json=_token_json(), status=200)
    # animals key missing; pagination missing too -> falls back to q['page']
    responses.add(responses.GET, f"{BASE_URL}/animals", json={}, status=200)
    c = PetfinderClient()
    out = list(c.iter_animals(type="cat"))
    assert out == []  # handled as empty without error


@responses.activate
def test_non_200_raises(creds_env: None) -> None:
    """Raise HTTPError on non-200 responses from the API."""

    responses.add(responses.POST, f"{BASE_URL}/oauth2/token", json=_token_json(), status=200)
    responses.add(responses.GET, f"{BASE_URL}/types", json={"oops": True}, status=500)
    c = PetfinderClient()
    with pytest.raises(requests.HTTPError):
        c.get_types()
