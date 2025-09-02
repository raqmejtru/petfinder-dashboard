# backend/app/pf_client.py
from __future__ import annotations

import os
import time
from typing import Any, cast
from collections.abc import Iterator

import requests


BASE_URL = "https://api.petfinder.com/v2"
ENV_CLIENT_ID = "PF_CLIENT_ID"
ENV_CLIENT_SECRET = "PF_CLIENT_SECRET"


class PetfinderAuthError(RuntimeError):
    """Raised when Petfinder credentials are missing or authentication fails."""


class PetfinderClient:
    """Thin API client for the Petfinder v2 REST API.

    Handles OAuth client-credentials flow, token caching/refresh, and simple
    pagination for common endpoints.

    Args:
        client_id: Petfinder API client ID. Defaults to env PF_CLIENT_ID.
        client_secret: Petfinder API client secret. Defaults to env PF_CLIENT_SECRET.
        timeout: Per-request timeout in seconds.

    Raises:
        PetfinderAuthError: If credentials are missing.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.client_id = client_id or os.getenv(ENV_CLIENT_ID)
        self.client_secret = client_secret or os.getenv(ENV_CLIENT_SECRET)
        if not self.client_id or not self.client_secret:
            raise PetfinderAuthError(
                f"Missing credentials: set {ENV_CLIENT_ID} and {ENV_CLIENT_SECRET}"
            )

        self._session = requests.Session()
        self._timeout = timeout
        self._token: str | None = None
        self._token_exp: float = 0.0  # epoch seconds

    # ------------------------- auth -------------------------

    def _ensure_token(self) -> None:
        """Fetch a new access token if missing or close to expiry."""
        # Reuse if we still have >60s left
        if self._token and (time.time() < self._token_exp - 60):
            return

        resp = self._session.post(
            f"{BASE_URL}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + int(data.get("expires_in", 3600))

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------- HTTP helpers -------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET with auth; on 401, refresh token once and retry."""
        url = f"{BASE_URL}{path}"
        resp = self._session.get(url, headers=self._headers(), params=params, timeout=self._timeout)
        if resp.status_code == 401:
            # token might be expired/invalid; refresh once
            self._token = None
            resp = self._session.get(
                url, headers=self._headers(), params=params, timeout=self._timeout
            )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    # ------------------------- Public API -------------------------

    def get_types(self) -> dict[str, Any]:
        """Return available animal types (simple sanity endpoint)."""
        return self._get("/types")

    def iter_animals(self, **params: Any) -> Iterator[dict[str, Any]]:
        """Yield animals across all pages for the given query parameters.

        Example:
            for a in client.iter_animals(type="cat", age="senior",
                                         gender="female", location="Austin, TX",
                                         distance=50, status="adoptable,adopted,found"):
                ...

        Notes:
            - Petfinder paginates results; this method follows pages until done.
            - Default page size is set to the API max (100) unless overridden.

        Args:
            **params: Query parameters documented by Petfinder's /animals endpoint,
                e.g. type, breed, age, gender, organization, location, distance,
                status, sort, page, limit (max 100), etc.

        Yields:
            dict: Each animal record (raw JSON dict from Petfinder).
        """
        q: dict[str, Any] = {"limit": 100, "page": 1}
        q.update(params)

        while True:
            data = self._get("/animals", params=q)

            for animal in data.get("animals", []):
                yield cast(dict[str, Any], animal)

            pg = data.get("pagination") or {}
            cur = int(pg.get("current_page", q["page"]))
            total = int(pg.get("total_pages", cur))

            if cur >= total:
                break

            q["page"] = cur + 1
