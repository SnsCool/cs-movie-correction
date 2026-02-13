"""Zoom recording download module.

Downloads cloud recordings from Zoom using Server-to-Server OAuth.

Environment variables required:
    ZOOM_ACCOUNT_ID   - Zoom account ID
    ZOOM_CLIENT_ID    - OAuth app client ID
    ZOOM_CLIENT_SECRET - OAuth app client secret
"""

import logging
import os
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE = "https://api.zoom.us/v2"

ACCEPTED_RECORDING_TYPES = {
    "shared_screen_with_speaker_view",
    "shared_screen_with_speaker_view(CC)",
    "active_speaker",
}


def get_access_token() -> str:
    """Obtain a Zoom Server-to-Server OAuth access token.

    Uses Basic authentication with ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET,
    posting to the Zoom OAuth endpoint with grant_type=account_credentials.

    Returns:
        The access token string.

    Raises:
        EnvironmentError: If required environment variables are missing.
        requests.HTTPError: If the token request fails.
    """
    account_id = os.environ.get("ZOOM_ACCOUNT_ID")
    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")

    missing = []
    if not account_id:
        missing.append("ZOOM_ACCOUNT_ID")
    if not client_id:
        missing.append("ZOOM_CLIENT_ID")
    if not client_secret:
        missing.append("ZOOM_CLIENT_SECRET")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    logger.info("Requesting Zoom OAuth access token")

    response = requests.post(
        ZOOM_OAUTH_URL,
        params={
            "grant_type": "account_credentials",
            "account_id": account_id,
        },
        auth=(client_id, client_secret),
        timeout=30,
    )
    response.raise_for_status()

    token = response.json()["access_token"]
    logger.info("Successfully obtained access token")
    return token


def list_recordings(from_date: str, to_date: str) -> list[dict]:
    """List Zoom cloud recordings within a date range.

    Fetches recordings for the authenticated user (``me``) and filters
    to MP4 files whose recording type is ``shared_screen_with_speaker_view``
    or ``active_speaker``.

    Args:
        from_date: Start date in ``YYYY-MM-DD`` format.
        to_date:   End date in ``YYYY-MM-DD`` format.

    Returns:
        A list of dicts, each containing:
            - meeting_id (int)
            - topic (str)
            - start_time (str)
            - recording_files (list[dict]) -- filtered MP4 entries

    Raises:
        requests.HTTPError: If the API request fails.
    """
    access_token = get_access_token()

    logger.info("Listing recordings from %s to %s", from_date, to_date)

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"from": from_date, "to": to_date, "page_size": 300}

    response = requests.get(
        f"{ZOOM_API_BASE}/users/me/recordings",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    meetings = data.get("meetings", [])

    results: list[dict] = []
    for meeting in meetings:
        filtered_files = [
            rf
            for rf in meeting.get("recording_files", [])
            if rf.get("file_type") == "MP4"
            and rf.get("recording_type") in ACCEPTED_RECORDING_TYPES
        ]

        if not filtered_files:
            continue

        results.append(
            {
                "meeting_id": meeting["id"],
                "topic": meeting.get("topic", ""),
                "start_time": meeting.get("start_time", ""),
                "recording_files": filtered_files,
            }
        )

    logger.info("Found %d meetings with matching recordings", len(results))
    return results


def download_recording(
    download_url: str, access_token: str, output_path: str
) -> str:
    """Download a Zoom recording MP4 file.

    Appends the access token as a query parameter and streams the file
    to ``output_path``.

    Args:
        download_url:  The download URL from the recording file entry.
        access_token:  A valid Zoom OAuth access token.
        output_path:   Local file path where the MP4 will be saved.

    Returns:
        The ``output_path`` string on success.

    Raises:
        requests.HTTPError: If the download request fails.
        OSError: If writing the file fails.
    """
    logger.info("Downloading recording to %s", output_path)

    response = requests.get(
        download_url,
        params={"access_token": access_token},
        stream=True,
        timeout=60,
    )
    response.raise_for_status()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    bytes_written = 0
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bytes_written += len(chunk)

    logger.info(
        "Download complete: %s (%.2f MB)",
        output_path,
        bytes_written / (1024 * 1024),
    )
    return output_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)

    from_date = thirty_days_ago.strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    logger.info("Fetching recordings from %s to %s", from_date, to_date)

    recordings = list_recordings(from_date, to_date)

    if not recordings:
        logger.info("No recordings found in the date range")
    else:
        for rec in recordings:
            print(f"\nMeeting: {rec['topic']}")
            print(f"  ID:    {rec['meeting_id']}")
            print(f"  Time:  {rec['start_time']}")
            print(f"  Files: {len(rec['recording_files'])}")
            for rf in rec["recording_files"]:
                print(
                    f"    - {rf.get('recording_type')} | "
                    f"{rf.get('file_size', 0) / (1024 * 1024):.1f} MB"
                )
