from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "")
    return v if v else default


def _load_or_create_fingerprint(session_file: Path) -> str:
    session_file.parent.mkdir(parents=True, exist_ok=True)
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            fingerprint = data.get("fingerprint")
            if isinstance(fingerprint, str) and fingerprint:
                return fingerprint
        except json.JSONDecodeError:
            pass
    fingerprint = secrets.token_hex(16)
    session_file.write_text(json.dumps({"fingerprint": fingerprint}, ensure_ascii=True, indent=2), encoding="utf-8")
    return fingerprint


def _save_session_data(session_file: Path, data: dict[str, Any]) -> None:
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _auto_get_token(session: requests.Session, base_url: str, session_file: Path, token_override: str) -> str:
    if token_override:
        return token_override

    parsed = urlparse(base_url)
    host = parsed.hostname or "www.imagetoword.info"
    fingerprint = _load_or_create_fingerprint(session_file)

    session.cookies.set("lang", "en", domain=host)
    session.cookies.set("deviceFingerprint", fingerprint, domain=host)

    signup_response = session.post(
        f"{base_url}/api/auth/fingerprint",
        json={"deviceFingerprint": fingerprint},
        timeout=30,
    )
    if signup_response.status_code not in {200, 400}:
        signup_response.raise_for_status()

    auth_response = session.post(
        f"{base_url}/api/collections/users/auth-with-password",
        json={"identity": fingerprint, "password": fingerprint},
        timeout=30,
    )
    auth_response.raise_for_status()
    payload = auth_response.json()
    token = payload.get("token")
    if not token:
        raise RuntimeError("Automatic auth succeeded without token in response.")

    record = payload.get("record") or {}
    _save_session_data(
        session_file,
        {
            "fingerprint": fingerprint,
            "user_id": record.get("id", ""),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    return token


def _upload_file(
    session: requests.Session,
    base_url: str,
    token: str,
    file_path: Path,
    output_format: str,
    model_type: str,
) -> str:
    url = f"{base_url}/api/upload"
    with file_path.open("rb") as handle:
        response = session.post(
            url,
            headers={"Authorization": token},
            data={"format": output_format, "model_type": model_type},
            files={"file": (file_path.name, handle)},
            timeout=120,
        )
    response.raise_for_status()
    data = response.json()
    file_id = data.get("fileId")
    if not file_id:
        raise RuntimeError(f"Unexpected upload response: {json.dumps(data)}")
    return file_id


def _get_upload_status(session: requests.Session, base_url: str, token: str, file_id: str) -> dict[str, Any]:
    response = session.get(
        f"{base_url}/api/collections/uploads/records/{file_id}",
        headers={"Authorization": token},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _wait_until_finished(
    session: requests.Session,
    base_url: str,
    token: str,
    file_id: str,
    poll_interval_seconds: float,
    poll_timeout_seconds: int,
) -> dict[str, Any]:
    start = time.time()
    while time.time() - start < poll_timeout_seconds:
        upload_record = _get_upload_status(session, base_url, token, file_id)
        status = (upload_record.get("status") or "unknown").lower()
        if status in {"completed", "failed"}:
            return upload_record
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Timeout waiting upload {file_id} to finish.")


def _find_result_record(session: requests.Session, base_url: str, token: str, file_id: str) -> dict[str, Any]:
    encoded_filter = quote(f'source=\"{file_id}\"', safe="")
    url = (
        f"{base_url}/api/collections/results/records"
        f"?page=1&perPage=1&sort=-created&filter={encoded_filter}"
    )
    response = session.get(url, headers={"Authorization": token}, timeout=60)
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"No result record found for source={file_id}")
    return items[0]


def _download_result_file(
    session: requests.Session, base_url: str, result_record: dict[str, Any], output_path: Path
) -> None:
    download_url = (
        f"{base_url}/api/files/"
        f"{result_record['collectionId']}/"
        f"{result_record['id']}/"
        f"{result_record['result_file']}"
    )
    response = session.get(download_url, timeout=120)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)


def _split_pages_best_effort(text: str) -> list[str]:
    # Many OCR pipelines separate pages with form-feed.
    if "\f" in text:
        parts = [p.strip() for p in text.split("\f")]
        parts = [p for p in parts if p]
        if parts:
            return parts
    # Fallback: treat whole document as a single page.
    return [text]


def extract_pages(pdf_path: Path) -> list[str]:
    """
    ImageToWord API OCR plugin.

    Env configuration:
    - IMAGETOWORD_BASE_URL (default: https://www.imagetoword.info)
    - IMAGETOWORD_TOKEN (optional override)
    - IMAGETOWORD_SESSION_FILE (default: .imagetoword-session.json)
    - IMAGETOWORD_MODEL_TYPE (default: manual)
    - IMAGETOWORD_POLL_INTERVAL_SECONDS (default: 2.0)
    - IMAGETOWORD_POLL_TIMEOUT_SECONDS (default: 300)
    """
    base_url = _env("IMAGETOWORD_BASE_URL", "https://www.imagetoword.info").rstrip("/")
    token_override = _env("IMAGETOWORD_TOKEN", "")
    session_file = Path(_env("IMAGETOWORD_SESSION_FILE", ".imagetoword-session.json")).resolve()
    model_type = _env("IMAGETOWORD_MODEL_TYPE", "manual")
    poll_interval_seconds = float(_env("IMAGETOWORD_POLL_INTERVAL_SECONDS", "2.0"))
    poll_timeout_seconds = int(_env("IMAGETOWORD_POLL_TIMEOUT_SECONDS", "300"))

    session = requests.Session()
    token = _auto_get_token(session, base_url, session_file, token_override)

    file_id = _upload_file(
        session=session,
        base_url=base_url,
        token=token,
        file_path=pdf_path,
        output_format="text",
        model_type=model_type,
    )

    upload_record = _wait_until_finished(
        session=session,
        base_url=base_url,
        token=token,
        file_id=file_id,
        poll_interval_seconds=poll_interval_seconds,
        poll_timeout_seconds=poll_timeout_seconds,
    )
    status = (upload_record.get("status") or "unknown").lower()
    if status != "completed":
        raise RuntimeError(f"ImageToWord processing failed: status={status}")

    result_record = _find_result_record(session, base_url, token, file_id)
    tmp_dir = Path(".imagetoword-tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"{pdf_path.stem}__imagetoword.txt"
    _download_result_file(session, base_url, result_record, out_path)

    text = out_path.read_text(encoding="utf-8", errors="ignore")
    return _split_pages_best_effort(text)

