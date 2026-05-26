from __future__ import annotations

from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


class SenderClient:
    def __init__(self, token: str | None, base_url: str = "https://api.sender.net/v2"):
        self.token = token
        self.base_url = base_url.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("SENDER_API_TOKEN is required when not using dry_run or Cloudflare Worker")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=30
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Sender request failed {response.status_code}: {response.text[:500]}")
        return response.json()

    def campaign(self, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        if mode == "dry_run":
            return {"success": True, "mode": "dry_run", "campaign_id": "dry-run"}
        create_payload = dict(payload)
        send_action = create_payload.pop("send_action", mode)
        schedule_time = create_payload.pop("schedule_time", None)
        created = self._post("/campaigns", create_payload)
        campaign_id = str(created.get("data", {}).get("id") or created.get("id") or "")
        if not campaign_id:
            raise RuntimeError(f"Sender did not return campaign id: {created}")
        if send_action == "schedule":
            scheduled = self._post(f"/campaigns/{campaign_id}/schedule", {"schedule_time": schedule_time})
            return {"success": True, "mode": "schedule", "campaign_id": campaign_id, "sender": scheduled}
        if send_action == "send":
            sent = self._post(f"/campaigns/{campaign_id}/send")
            return {"success": True, "mode": "send", "campaign_id": campaign_id, "sender": sent}
        return {"success": True, "mode": "draft", "campaign_id": campaign_id, "sender": created}

    def transactional(self, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        if mode == "dry_run":
            return {"success": True, "mode": "dry_run", "emailId": "dry-run"}
        return self._post("/message/send", payload)
