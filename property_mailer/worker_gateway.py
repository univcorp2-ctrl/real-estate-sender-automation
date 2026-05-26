from __future__ import annotations

from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


class CloudflareWorkerGateway:
    def __init__(self, base_url: str, shared_secret: str):
        self.base_url = base_url.rstrip("/")
        self.shared_secret = shared_secret

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.shared_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"Worker request failed {response.status_code}: {response.text[:500]}")
        return response.json()

    def acquire_lock(self, key: str, ttl_seconds: int = 1800) -> bool:
        return bool(self._post("/lock/acquire", {"key": key, "ttl_seconds": ttl_seconds}).get("acquired"))

    def release_lock(self, key: str) -> None:
        self._post("/lock/release", {"key": key})

    def filter_unsent(self, audience_key: str, fingerprints: list[str]) -> list[str]:
        data = self._post(
            "/state/filter-unsent", {"audience_key": audience_key, "fingerprints": fingerprints}
        )
        return list(data.get("unsent", []))

    def mark_sent(self, audience_key: str, records: list[dict[str, str]]) -> None:
        self._post("/state/mark-sent", {"audience_key": audience_key, "records": records})

    def send_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/sender/campaign", payload)

    def send_transactional(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/sender/transactional", payload)
