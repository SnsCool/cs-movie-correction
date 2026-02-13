"""Main pipeline orchestrator for SNS Club Portal automation.

Integrates Zoom recording download, Notion record matching, silence trimming,
thumbnail generation, YouTube upload, and Discord notification into a single
automated pipeline.

Pipeline flow:
    1. Retry error records from Notion (retry_count < 3)
    2. Fetch Zoom recordings from the last 24 hours
    3. For each recording: match, download, trim, thumbnail, upload, notify
    4. On error: update Notion status; escalate after 3 retries
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup – ensure src/ is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import discord as discord_mod  # noqa: E402  (renamed to avoid stdlib clash)
import notion                  # noqa: E402
import thumbnail               # noqa: E402
import trim                    # noqa: E402
import youtube                 # noqa: E402
import zoom                    # noqa: E402

logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 3


# ---------------------------------------------------------------------------
# Single-recording processing
# ---------------------------------------------------------------------------


def _process_recording(
    record: dict,
    recording_file: dict,
    tmp_dir: str,
) -> None:
    """Process one Zoom recording end-to-end.

    Steps executed:
        1. Update Notion status to "処理中"
        2. Download the Zoom recording
        3. Auto-trim leading/trailing silence
        4. Generate a thumbnail image
        5. Upload to YouTube and set thumbnail
        6. Send Discord notification (failure is swallowed)
        7. Create a video archive record in Notion
        8. Update Notion master status to "完了"

    On any error (except Discord), the exception propagates to the caller
    so that the master record can be marked as "エラー".

    Args:
        record:         Parsed Notion master record dict.
        recording_file: A single Zoom recording file entry dict containing
                        ``download_url`` (and other metadata).
        tmp_dir:        Path to a temporary directory for downloaded files.
    """
    page_id = record["page_id"]
    title = record["title"]

    # 1. Mark as processing ------------------------------------------------
    notion.update_status(page_id, "処理中")

    # 2. Download Zoom recording -------------------------------------------
    download_url = recording_file["download_url"]
    access_token = zoom.get_access_token()
    raw_path = os.path.join(tmp_dir, f"{page_id}_raw.mp4")
    zoom.download_recording(download_url, access_token, raw_path)
    logger.info("Downloaded recording for '%s' to %s", title, raw_path)

    # 3. Auto-trim silence -------------------------------------------------
    trimmed_path = os.path.join(tmp_dir, f"{page_id}_trimmed.mp4")
    trimmed_path = trim.auto_trim(raw_path, trimmed_path)
    logger.info("Trimmed video: %s", trimmed_path)

    # 4. Generate thumbnail ------------------------------------------------
    thumbnail_path = thumbnail.generate_thumbnail(
        record, base_dir=str(PROJECT_ROOT)
    )
    logger.info("Generated thumbnail: %s", thumbnail_path)

    # 5. Upload to YouTube -------------------------------------------------
    video_id = youtube.upload_video(
        file_path=trimmed_path,
        title=title,
        description=record.get("notes", ""),
    )
    youtube_url = youtube.get_video_url(video_id)
    logger.info("Uploaded to YouTube: %s", youtube_url)

    youtube.set_thumbnail(video_id, thumbnail_path)
    logger.info("Thumbnail set for video %s", video_id)

    # 6. Discord notification (never fail) ---------------------------------
    # Build Notion page URL from page_id
    notion_page_url = f"https://notion.so/{page_id.replace('-', '')}"
    # Use YouTube auto-generated thumbnail for Discord embed
    discord_thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    discord_mod.send_notification(
        title=title,
        youtube_url=youtube_url,
        thumbnail_url=discord_thumbnail_url,
        lecturer=record.get("lecturer_name", ""),
        category=record.get("category", ""),
        notion_url=notion_page_url,
        genre=record.get("genre", ""),
        thumbnail_text=record.get("thumbnail_text", ""),
        student_name=record.get("student_name", ""),
    )

    # 7. Create video archive record ---------------------------------------
    start_date = record.get("start_time", "")[:10]  # ISO date portion
    # Use YouTube's auto-generated thumbnail as the Notion サムネイル
    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    notion.create_video_record(
        title=title,
        category=record.get("category", ""),
        date=start_date,
        lecturer=record.get("lecturer_name", ""),
        youtube_url=youtube_url,
        thumbnail_url=thumbnail_url,
    )
    logger.info("Created video archive record for '%s'", title)

    # 8. Mark master record as complete ------------------------------------
    notion.update_status(page_id, "完了", youtube_url=youtube_url)
    logger.info("Pipeline complete for '%s'", title)


# ---------------------------------------------------------------------------
# Processing wrapper with error handling
# ---------------------------------------------------------------------------


def _safe_process(
    record: dict,
    recording_file: dict,
    tmp_dir: str,
) -> None:
    """Wrap :func:`_process_recording` with error handling and Notion updates.

    On failure the master record is updated to "エラー" (or "要手動対応"
    when the retry count has reached the maximum).

    Args:
        record:         Parsed Notion master record dict.
        recording_file: A single Zoom recording file entry dict.
        tmp_dir:        Temporary directory for downloads.
    """
    page_id = record["page_id"]
    title = record.get("title", "(unknown)")

    try:
        _process_recording(record, recording_file, tmp_dir)
    except Exception as exc:
        logger.exception("Error processing '%s' (page_id=%s)", title, page_id)

        retry_count = record.get("retry_count", 0)
        error_msg = str(exc)

        if retry_count + 1 >= MAX_RETRY_COUNT:
            target_status = "要手動対応"
        else:
            target_status = "エラー"

        try:
            notion.update_status(page_id, target_status, error_msg=error_msg)
        except Exception:
            logger.exception(
                "Failed to update Notion status for page_id=%s", page_id
            )


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------


def run_pipeline() -> None:
    """Execute the full automation pipeline.

    1. Retry previously failed records (ステータス=エラー, retry < 3).
    2. Fetch new Zoom recordings from the last 24 hours.
    3. Match each recording with a Notion master record.
    4. Process each matched recording independently.

    All recordings are processed in isolation -- one failure does not
    prevent subsequent recordings from being processed.  Temporary files
    are cleaned up at the end regardless of success or failure.
    """
    tmp_dir = tempfile.mkdtemp(prefix="cs_movie_")
    logger.info("Temporary directory: %s", tmp_dir)

    try:
        # ---- Phase 1: retry error records --------------------------------
        logger.info("=== Phase 1: Retrying error records ===")
        try:
            error_records = notion.find_error_records()
        except Exception:
            logger.exception("Failed to fetch error records from Notion")
            error_records = []

        for record in error_records:
            logger.info(
                "Retrying error record: page_id=%s title=%s (retry #%d)",
                record["page_id"],
                record["title"],
                record.get("retry_count", 0) + 1,
            )
            # For retry records we don't have a specific recording_file from
            # Zoom.  Re-fetch recordings to find a match.
            try:
                start_time = record.get("start_time", "")
                if not start_time:
                    logger.warning(
                        "No start_time on error record %s; skipping",
                        record["page_id"],
                    )
                    continue

                zoom_dt = datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                )
                from_date = (zoom_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                to_date = (zoom_dt + timedelta(days=1)).strftime("%Y-%m-%d")

                recordings = zoom.list_recordings(from_date, to_date)
                matched_file = _find_recording_file_for_record(
                    record, recordings
                )
                if not matched_file:
                    logger.warning(
                        "No Zoom recording found for retry record %s",
                        record["page_id"],
                    )
                    continue

                _safe_process(record, matched_file, tmp_dir)
            except Exception:
                logger.exception(
                    "Unexpected error during retry of %s", record["page_id"]
                )

        # ---- Phase 2: process new recordings -----------------------------
        logger.info("=== Phase 2: Processing new Zoom recordings ===")
        today = datetime.now()
        from_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")

        try:
            recordings = zoom.list_recordings(from_date, to_date)
        except Exception:
            logger.exception("Failed to list Zoom recordings")
            recordings = []

        logger.info("Found %d meeting(s) with recordings", len(recordings))

        for meeting in recordings:
            start_time = meeting.get("start_time", "")
            topic = meeting.get("topic", "")
            logger.info(
                "Processing meeting: topic='%s' start_time=%s",
                topic,
                start_time,
            )

            # Match with Notion master DB
            try:
                record = notion.find_matching_record(start_time)
            except Exception:
                logger.exception(
                    "Failed to query Notion for meeting '%s'", topic
                )
                continue

            if record is None:
                logger.info(
                    "No matching Notion record for '%s' at %s; skipping",
                    topic,
                    start_time,
                )
                continue

            # Process each recording file for this meeting
            for rec_file in meeting.get("recording_files", []):
                _safe_process(record, rec_file, tmp_dir)

    finally:
        # Clean up temporary files
        logger.info("Cleaning up temporary directory: %s", tmp_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_recording_file_for_record(
    record: dict,
    recordings: list[dict],
) -> dict | None:
    """Find a Zoom recording file that matches a Notion record's start time.

    Compares the record's ``start_time`` against each meeting's
    ``start_time`` within a 30-minute window.

    Args:
        record:     Parsed Notion master record dict.
        recordings: List of meetings returned by :func:`zoom.list_recordings`.

    Returns:
        The first matching recording file dict, or ``None``.
    """
    record_start = record.get("start_time", "")
    if not record_start:
        return None

    record_dt = datetime.fromisoformat(record_start.replace("Z", "+00:00"))

    for meeting in recordings:
        meeting_start = meeting.get("start_time", "")
        if not meeting_start:
            continue

        meeting_dt = datetime.fromisoformat(
            meeting_start.replace("Z", "+00:00")
        )

        if abs((meeting_dt - record_dt).total_seconds()) <= 1800:
            files = meeting.get("recording_files", [])
            if files:
                return files[0]

    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting SNS Club Portal automation pipeline")
    logger.info("Project root: %s", PROJECT_ROOT)

    run_pipeline()

    logger.info("Pipeline finished")
