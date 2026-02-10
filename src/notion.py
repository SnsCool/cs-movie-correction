"""Notion API module for SNS Club Portal - 動画管理システム.

Provides functions to interact with the Notion master table and video archive DB
for the automated Zoom recording pipeline.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_MASTER_DB_ID = os.environ.get(
    "NOTION_MASTER_DB_ID", "300f3b0f-ba85-81a7-b097-e41110ce3148"
)
NOTION_VIDEO_DB_ID = os.environ.get(
    "NOTION_VIDEO_DB_ID", "301f3b0f-ba85-815a-a696-d4836fe88bb6"
)

BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict[str, str]:
    """Return common request headers for the Notion API."""
    token = os.environ.get("NOTION_TOKEN", "") or NOTION_TOKEN
    if not token:
        raise RuntimeError("NOTION_TOKEN environment variable is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Internal helpers – property value extractors
# ---------------------------------------------------------------------------


def _get_title(prop: dict) -> str:
    """Extract plain text from a title property."""
    parts = prop.get("title", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _get_rich_text(prop: dict) -> str:
    """Extract plain text from a rich_text property."""
    parts = prop.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _get_select(prop: dict) -> str:
    """Extract the name from a select property."""
    sel = prop.get("select")
    if sel is None:
        return ""
    return sel.get("name", "")


def _get_number(prop: dict) -> int:
    """Extract value from a number property (default 0)."""
    val = prop.get("number")
    if val is None:
        return 0
    return int(val)


def _get_url(prop: dict) -> str:
    """Extract value from a url property."""
    return prop.get("url") or ""


def _get_date(prop: dict) -> str:
    """Extract the start string from a date property."""
    date_obj = prop.get("date")
    if date_obj is None:
        return ""
    return date_obj.get("start", "")


def _get_files(prop: dict) -> str:
    """Extract the first file URL from a files property."""
    files = prop.get("files", [])
    if not files:
        return ""
    f = files[0]
    if f.get("type") == "file":
        return f.get("file", {}).get("url", "")
    if f.get("type") == "external":
        return f.get("external", {}).get("url", "")
    return f.get("name", "")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def parse_master_record(page: dict) -> dict:
    """Parse a Notion page object from the master table into a clean dict.

    Parameters
    ----------
    page:
        A full Notion page object as returned by the API.

    Returns
    -------
    dict with the following keys:
        page_id, title, thumbnail_text, category, start_time, lecturer_name,
        lecturer_image1, lecturer_image2, genre, pattern, student_name,
        notes, status, retry_count
    """
    props: dict[str, Any] = page.get("properties", {})

    return {
        "page_id": page.get("id", ""),
        "title": _get_title(props.get("タイトル", {})),
        "thumbnail_text": _get_rich_text(props.get("サムネ文言", {})),
        "category": _get_select(props.get("種別", {})),
        "start_time": _get_date(props.get("開始時間", {})),
        "lecturer_name": _get_rich_text(props.get("講師名", {})),
        "lecturer_image1": _get_select(props.get("講師画像①", {})),
        "lecturer_image2": _get_select(props.get("講師画像②", {})),
        "genre": _get_select(props.get("ジャンル", {})),
        "pattern": _get_select(props.get("パターン", {})),
        "student_name": _get_rich_text(props.get("生徒名", {})),
        "notes": _get_rich_text(props.get("補足情報", {})),
        "status": _get_select(props.get("ステータス", {})),
        "retry_count": _get_number(props.get("リトライ回数", {})),
    }


def find_matching_record(zoom_start_time: str) -> dict | None:
    """Query the master DB for a record matching a Zoom start time.

    The match criteria are:
    - ステータス = "入力済み"
    - 開始時間 is within +/- 30 minutes of *zoom_start_time*

    Parameters
    ----------
    zoom_start_time:
        An ISO 8601 datetime string representing the Zoom meeting start time.

    Returns
    -------
    A parsed record dict (via :func:`parse_master_record`) for the first
    matching page, or ``None`` if no match is found.
    """
    zoom_dt = dateutil_parser.isoparse(zoom_start_time)
    # Ensure timezone-aware (assume UTC if naive)
    if zoom_dt.tzinfo is None:
        zoom_dt = zoom_dt.replace(tzinfo=timezone.utc)

    window_start = zoom_dt - timedelta(minutes=30)
    window_end = zoom_dt + timedelta(minutes=30)

    payload: dict[str, Any] = {
        "filter": {
            "and": [
                {
                    "property": "ステータス",
                    "select": {"equals": "入力済み"},
                },
                {
                    "property": "開始時間",
                    "date": {"on_or_after": window_start.isoformat()},
                },
                {
                    "property": "開始時間",
                    "date": {"on_or_before": window_end.isoformat()},
                },
            ]
        },
        "page_size": 10,
    }

    url = f"{BASE_URL}/databases/{NOTION_MASTER_DB_ID}/query"
    logger.info(
        "Querying master DB for records matching zoom_start_time=%s (window: %s ~ %s)",
        zoom_start_time,
        window_start.isoformat(),
        window_end.isoformat(),
    )

    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if not results:
        logger.warning("No matching record found for zoom_start_time=%s", zoom_start_time)
        return None

    page = results[0]
    record = parse_master_record(page)
    logger.info("Matched record: page_id=%s title=%s", record["page_id"], record["title"])
    return record


def update_status(
    page_id: str,
    status: str,
    error_msg: str = "",
    youtube_url: str = "",
) -> None:
    """Update a master record's status and related fields.

    Parameters
    ----------
    page_id:
        The Notion page ID to update.
    status:
        New value for ステータス (e.g. "処理中", "完了", "エラー", "要手動対応").
    error_msg:
        Error description to write to エラー内容. Pass empty string to clear.
    youtube_url:
        YouTube URL to write to YouTubeリンク. Pass empty string to skip.
    """
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    properties: dict[str, Any] = {
        "ステータス": {"select": {"name": status}},
        "処理日時": {"date": {"start": now_iso}},
    }

    # エラー内容 - always set (clear on success, set on error)
    properties["エラー内容"] = {
        "rich_text": [{"text": {"content": error_msg}}] if error_msg else [],
    }

    # YouTubeリンク
    if youtube_url:
        properties["YouTubeリンク"] = {"url": youtube_url}

    # Increment リトライ回数 on error – need to read current value first
    if status == "エラー" or status == "要手動対応":
        current = _get_current_retry_count(page_id)
        properties["リトライ回数"] = {"number": current + 1}

    url = f"{BASE_URL}/pages/{page_id}"
    payload: dict[str, Any] = {"properties": properties}

    logger.info("Updating page %s: status=%s", page_id, status)
    resp = requests.patch(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    logger.info("Successfully updated page %s", page_id)


def _get_current_retry_count(page_id: str) -> int:
    """Fetch the current リトライ回数 for a page."""
    url = f"{BASE_URL}/pages/{page_id}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    page = resp.json()
    props = page.get("properties", {})
    return _get_number(props.get("リトライ回数", {}))


def create_video_record(
    title: str,
    category: str,
    date: str,
    lecturer: str,
    youtube_url: str,
    thumbnail_url: str = "",
) -> str:
    """Create a new record in the 動画アーカイブ DB and embed a YouTube video block.

    Parameters
    ----------
    title:
        Video title (タイトル).
    category:
        Video category / 種別 (e.g. "1on1添削", "グループコンサル").
    date:
        Date string in ISO 8601 format (日付).
    lecturer:
        Lecturer name (講師名) as a select value.
    youtube_url:
        YouTube video URL (YouTubeリンク).
    thumbnail_url:
        Optional external URL for the thumbnail image (サムネイル).

    Returns
    -------
    The page_id of the newly created record.
    """
    properties: dict[str, Any] = {
        "動画タイトル": {"title": [{"text": {"content": title}}]},
        "タグ": {"select": {"name": category}},
        "日付": {"date": {"start": date}},
        "講師名": {"select": {"name": lecturer}},
        "YouTubeリンク": {"url": youtube_url},
    }

    if thumbnail_url:
        properties["サムネイル"] = {
            "files": [
                {
                    "name": "thumbnail.png",
                    "type": "external",
                    "external": {"url": thumbnail_url},
                }
            ]
        }

    # Build the YouTube embed block to add as page content
    children: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "video",
            "video": {
                "type": "external",
                "external": {"url": youtube_url},
            },
        }
    ]

    payload: dict[str, Any] = {
        "parent": {"database_id": NOTION_VIDEO_DB_ID},
        "properties": properties,
        "children": children,
    }

    url = f"{BASE_URL}/pages"
    logger.info("Creating video record: title=%s category=%s", title, category)
    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()

    page = resp.json()
    page_id = page["id"]
    logger.info("Created video record: page_id=%s", page_id)
    return page_id


def find_error_records() -> list[dict]:
    """Find master records with ステータス=エラー and リトライ回数 < 3.

    Returns
    -------
    A list of parsed record dicts (via :func:`parse_master_record`).
    """
    payload: dict[str, Any] = {
        "filter": {
            "and": [
                {
                    "property": "ステータス",
                    "select": {"equals": "エラー"},
                },
                {
                    "property": "リトライ回数",
                    "number": {"less_than": 3},
                },
            ]
        },
        "page_size": 100,
    }

    url = f"{BASE_URL}/databases/{NOTION_MASTER_DB_ID}/query"
    logger.info("Querying master DB for error records (retry_count < 3)")

    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    records = [parse_master_record(page) for page in results]
    logger.info("Found %d error records eligible for retry", len(records))
    return records
