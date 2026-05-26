from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .data_loader import load_properties_from_path, load_recipients_from_path
from .drive_loader import load_latest_properties_from_drive
from .local_state import LocalStateStore
from .models import CampaignPlan, Property, ValidationIssue
from .render import render_campaign, render_inquiry_reply, schedule_time_jst
from .sender_client import SenderClient
from .validation import (
    ACTIVE_STATUSES,
    has_errors,
    validate_campaign_render,
    validate_properties,
    validate_recipients,
)
from .worker_gateway import CloudflareWorkerGateway


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _load_properties(config: Config) -> list[Property]:
    if config.property_source_mode == "google_drive":
        if not config.google_drive_folder_id or not config.google_service_account_json:
            raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID and GOOGLE_SERVICE_ACCOUNT_JSON are required")
        return load_latest_properties_from_drive(
            config.google_drive_folder_id, config.google_service_account_json
        )
    return load_properties_from_path(config.local_properties_path)


def _state(config: Config):
    if config.worker_base_url and config.worker_shared_secret:
        return CloudflareWorkerGateway(config.worker_base_url, config.worker_shared_secret)
    return LocalStateStore(config.database_path)


def _send_campaign(config: Config, plan: CampaignPlan) -> dict[str, Any]:
    payload = {
        "title": plan.title,
        "subject": plan.subject,
        "from": config.sender_from_name,
        "reply_to": config.sender_reply_to,
        "preheader": plan.preheader,
        "content_type": "html",
        "google_analytics": 1,
        "groups": config.sender_group_ids,
        "segments": config.sender_segment_ids,
        "content": plan.html,
        "send_action": config.sender_send_mode,
        "schedule_time": schedule_time_jst(config),
    }
    if config.worker_base_url and config.worker_shared_secret:
        return CloudflareWorkerGateway(config.worker_base_url, config.worker_shared_secret).send_campaign(
            payload
        )
    return SenderClient(config.sender_api_token).campaign(payload, config.sender_send_mode)


def _send_transactional(config: Config, payload: dict[str, Any]) -> dict[str, Any]:
    if config.worker_base_url and config.worker_shared_secret:
        return CloudflareWorkerGateway(
            config.worker_base_url, config.worker_shared_secret
        ).send_transactional(payload)
    return SenderClient(config.sender_api_token).transactional(payload, config.sender_send_mode)


def _serialize_issues(issues: list[ValidationIssue]) -> list[dict[str, str | None]]:
    return [issue.__dict__ for issue in issues]


def run_daily(config: Config, *, dry_run: bool = False, verify_only: bool = False) -> dict[str, Any]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        config.sender_send_mode = "dry_run"

    state = _state(config)
    lock_key = "property-mailer-daily"
    if not state.acquire_lock(lock_key):
        result = {"status": "skipped", "reason": "another job is running"}
        _write_json(config.out_dir / "run-result.json", result)
        return result

    try:
        all_properties = _load_properties(config)
        recipients = load_recipients_from_path(config.local_recipients_path)
        data_issues = validate_properties(all_properties) + validate_recipients(recipients)
        active_properties = [p for p in all_properties if p.status in ACTIVE_STATUSES]
        active_properties.sort(key=lambda p: p.updated_at, reverse=True)
        active_properties = active_properties[: config.max_properties_per_campaign]

        preliminary = render_campaign(active_properties, config)
        candidate_fingerprints = list(preliminary.fingerprints.values())
        unsent_fingerprints = set(state.filter_unsent(config.audience_key, candidate_fingerprints))
        selected = [
            prop for prop in active_properties if preliminary.fingerprints[prop.property_id] in unsent_fingerprints
        ]

        if not selected:
            result = {
                "status": "noop",
                "reason": "no new properties for this audience",
                "data_issues": _serialize_issues(data_issues),
            }
            _write_json(config.out_dir / "run-result.json", result)
            return result

        plan = render_campaign(selected, config)
        render_issues = validate_campaign_render(plan)
        all_issues = data_issues + render_issues
        _write_json(config.out_dir / "validation-issues.json", _serialize_issues(all_issues))
        (config.out_dir / "campaign.html").write_text(plan.html, encoding="utf-8")
        (config.out_dir / "campaign.txt").write_text(plan.text, encoding="utf-8")
        _write_json(
            config.out_dir / "campaign-plan.json",
            {
                "title": plan.title,
                "subject": plan.subject,
                "audience_key": plan.audience_key,
                "property_ids": [p.property_id for p in plan.properties],
                "fingerprints": plan.fingerprints,
            },
        )

        if has_errors(all_issues) and config.validation_strict:
            result = {"status": "failed_validation", "issues": _serialize_issues(all_issues)}
            _write_json(config.out_dir / "run-result.json", result)
            raise RuntimeError("Validation failed; see out/validation-issues.json")

        if verify_only or config.require_manual_approval:
            result = {"status": "verified", "send_skipped": True, "issues": _serialize_issues(all_issues)}
            _write_json(config.out_dir / "run-result.json", result)
            return result

        sender_result = _send_campaign(config, plan)
        campaign_id = str(sender_result.get("campaign_id") or sender_result.get("data", {}).get("id") or "")
        status = "dry_run" if config.sender_send_mode == "dry_run" else config.sender_send_mode
        if config.sender_send_mode != "dry_run" or config.record_dry_runs:
            now = datetime.now(timezone.utc).isoformat()
            state.mark_sent(
                config.audience_key,
                [
                    {
                        "fingerprint": plan.fingerprints[prop.property_id],
                        "property_id": prop.property_id,
                        "campaign_id": campaign_id,
                        "status": status,
                        "sent_at": now,
                    }
                    for prop in plan.properties
                ],
            )

        result = {
            "status": "sent" if config.sender_send_mode == "send" else status,
            "sender_result": sender_result,
            "property_ids": [p.property_id for p in plan.properties],
            "issues": _serialize_issues(all_issues),
        }
        _write_json(config.out_dir / "run-result.json", result)
        return result
    finally:
        state.release_lock(lock_key)


def reply_inquiry(config: Config, payload: dict[str, Any]) -> dict[str, Any]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    properties = _load_properties(config)
    prop = next((p for p in properties if p.property_id == str(payload.get("property_id"))), None)
    if prop is None:
        raise RuntimeError(f"property_id not found: {payload.get('property_id')}")
    issues = validate_properties([prop])
    if has_errors(issues) and config.validation_strict:
        _write_json(config.out_dir / "inquiry-validation-issues.json", _serialize_issues(issues))
        raise RuntimeError("Inquiry reply validation failed")

    email = str(payload.get("email") or "").strip()
    name = str(payload.get("name") or "").strip() or None
    subject, text, html = render_inquiry_reply(prop, name)
    attachments = {f"{prop.property_id}.pdf": prop.brochure_url} if prop.brochure_url else {}
    message = {
        "from": {"email": config.sender_from_email, "name": config.sender_from_name},
        "to": {"email": email, "name": name or ""},
        "subject": subject,
        "text": text,
        "html": html,
        "headers": {"charset": "utf-8"},
        "variables": {"property_id": prop.property_id},
        "attachments": attachments,
    }
    _write_json(config.out_dir / "inquiry-message.json", message)
    result = _send_transactional(config, message)
    _write_json(config.out_dir / "inquiry-result.json", result)
    return result
