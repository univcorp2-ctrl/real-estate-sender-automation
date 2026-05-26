from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Config:
    property_source_mode: str
    local_properties_path: Path
    local_recipients_path: Path | None
    google_drive_folder_id: str | None
    google_service_account_json: str | None
    database_path: Path
    out_dir: Path
    worker_base_url: str | None
    worker_shared_secret: str | None
    sender_api_token: str | None
    sender_from_email: str
    sender_from_name: str
    sender_reply_to: str
    sender_group_ids: list[str]
    sender_segment_ids: list[str]
    sender_send_mode: str
    sender_schedule_time_jst: str
    max_properties_per_campaign: int
    require_manual_approval: bool
    record_dry_runs: bool
    validation_strict: bool

    @property
    def audience_key(self) -> str:
        if self.sender_segment_ids:
            return "segments:" + ",".join(sorted(self.sender_segment_ids))
        if self.sender_group_ids:
            return "groups:" + ",".join(sorted(self.sender_group_ids))
        return "local-recipient-list"


def load_config() -> Config:
    load_dotenv()
    out_dir = Path(os.getenv("OUT_DIR", "out"))
    recipients_path = os.getenv("LOCAL_RECIPIENTS_PATH", "data/sample_recipients.csv")
    return Config(
        property_source_mode=os.getenv("PROPERTY_SOURCE_MODE", "local"),
        local_properties_path=Path(os.getenv("LOCAL_PROPERTIES_PATH", "data/sample_properties.csv")),
        local_recipients_path=Path(recipients_path) if recipients_path else None,
        google_drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID"),
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        database_path=Path(os.getenv("DATABASE_PATH", str(out_dir / "local-state.sqlite3"))),
        out_dir=out_dir,
        worker_base_url=os.getenv("AUTOMATION_WORKER_URL") or os.getenv("WORKER_BASE_URL"),
        worker_shared_secret=os.getenv("WORKER_SHARED_SECRET"),
        sender_api_token=os.getenv("SENDER_API_TOKEN"),
        sender_from_email=os.getenv("SENDER_FROM_EMAIL", "info@example.com"),
        sender_from_name=os.getenv("SENDER_FROM_NAME", "Real Estate Team"),
        sender_reply_to=os.getenv("SENDER_REPLY_TO", os.getenv("SENDER_FROM_EMAIL", "info@example.com")),
        sender_group_ids=_csv("SENDER_GROUP_IDS"),
        sender_segment_ids=_csv("SENDER_SEGMENT_IDS"),
        sender_send_mode=os.getenv("SENDER_SEND_MODE", "dry_run"),
        sender_schedule_time_jst=os.getenv("SENDER_SCHEDULE_TIME_JST", "10:00"),
        max_properties_per_campaign=int(os.getenv("MAX_PROPERTIES_PER_CAMPAIGN", "10")),
        require_manual_approval=_bool("REQUIRE_MANUAL_APPROVAL", False),
        record_dry_runs=_bool("RECORD_DRY_RUNS", False),
        validation_strict=_bool("VALIDATION_STRICT", True),
    )
