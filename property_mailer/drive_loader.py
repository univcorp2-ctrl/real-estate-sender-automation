from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from .data_loader import load_properties_from_path
from .models import Property

SUPPORTED_MIME_SUFFIX = {
    "text/csv": ".csv",
    "application/json": ".json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def load_latest_properties_from_drive(folder_id: str, service_account_json: str) -> list[Property]:
    """Download the newest supported property file from a Google Drive folder."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    query = f"'{folder_id}' in parents and trashed = false"
    response = (
        service.files()
        .list(
            q=query,
            pageSize=50,
            fields="files(id,name,mimeType,modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    files = response.get("files", [])
    supported = [item for item in files if item.get("mimeType") in SUPPORTED_MIME_SUFFIX]
    if not supported:
        raise RuntimeError("No supported CSV/JSON/XLSX property file found in Google Drive folder")

    latest = supported[0]
    request = service.files().get_media(fileId=latest["id"])
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    suffix = SUPPORTED_MIME_SUFFIX[latest["mimeType"]]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(buffer.getvalue())
        tmp_path = Path(tmp.name)
    try:
        return load_properties_from_path(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
