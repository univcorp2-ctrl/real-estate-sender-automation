from pathlib import Path

from property_mailer.config import Config
from property_mailer.orchestrator import run_daily


def _config(tmp_path: Path) -> Config:
    return Config(
        property_source_mode="local",
        local_properties_path=Path("data/sample_properties.csv"),
        local_recipients_path=Path("data/sample_recipients.csv"),
        google_drive_folder_id=None,
        google_service_account_json=None,
        database_path=tmp_path / "state.sqlite3",
        out_dir=tmp_path / "out",
        worker_base_url=None,
        worker_shared_secret=None,
        sender_api_token=None,
        sender_from_email="info@example.com",
        sender_from_name="Example Realty",
        sender_reply_to="info@example.com",
        sender_group_ids=["group1"],
        sender_segment_ids=[],
        sender_send_mode="dry_run",
        sender_schedule_time_jst="10:00",
        max_properties_per_campaign=5,
        require_manual_approval=False,
        record_dry_runs=True,
        validation_strict=True,
    )


def test_run_daily_dry_run_and_dedupes(tmp_path):
    config = _config(tmp_path)
    first = run_daily(config, dry_run=True)
    assert first["status"] == "dry_run"
    assert first["property_ids"] == ["P-1002", "P-1001"]

    second = run_daily(config, dry_run=True)
    assert second["status"] == "noop"
