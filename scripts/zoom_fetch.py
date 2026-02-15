#!/usr/bin/env python3
"""
Fetch Zoom cloud recordings using Server-to-Server OAuth flow.

Steps:
1. Obtain access token via account_credentials grant
2. List cloud recordings for the authenticated user
3. Print meeting topics, dates, file types, sizes, and download URLs
"""

import json
import requests
import sys
from datetime import datetime


# ── Credentials ──────────────────────────────────────────────────────────────
ZOOM_ACCOUNT_ID = "_0lxDkFUSWWt036mTe7EyA"
ZOOM_CLIENT_ID = "0w88q95iSQ60RlF55HcKw"
ZOOM_CLIENT_SECRET = "UoHJR5heoQzV7XV62RLtYuwZ3jtILW2S"


# ── Step 1: Get OAuth token ──────────────────────────────────────────────────
def get_access_token() -> str:
    """Obtain an access token using Server-to-Server OAuth (account_credentials)."""
    url = "https://zoom.us/oauth/token"
    params = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID,
    }
    resp = requests.post(
        url,
        params=params,
        auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        print(f"[ERROR] Failed to obtain access token: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    data = resp.json()
    print("=== OAuth Token Response ===")
    print(f"  token_type : {data.get('token_type')}")
    print(f"  expires_in : {data.get('expires_in')} seconds")
    print(f"  scope      : {data.get('scope')}")
    print()
    return data["access_token"]


# ── Step 2: List cloud recordings ────────────────────────────────────────────
def list_recordings(token: str) -> dict:
    """Fetch cloud recordings from Zoom API."""
    url = "https://api.zoom.us/v2/users/me/recordings"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "from": "2024-01-01",
        "to": datetime.now().strftime("%Y-%m-%d"),
        "page_size": 300,
    }
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        print(f"[ERROR] Failed to list recordings: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    return resp.json()


# ── Step 3: Pretty-print results ─────────────────────────────────────────────
def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes is None:
        return "N/A"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_recordings(data: dict):
    """Print recordings in a readable format."""
    meetings = data.get("meetings", [])
    total = data.get("total_records", 0)

    print(f"=== Cloud Recordings: {total} meeting(s) found ===")
    print()

    if not meetings:
        print("  (no recordings found)")
        return

    for i, meeting in enumerate(meetings, 1):
        topic = meeting.get("topic", "(no topic)")
        start = meeting.get("start_time", "N/A")
        duration = meeting.get("duration", 0)
        meeting_id = meeting.get("id", "N/A")

        print(f"── Meeting {i}: {topic} ──")
        print(f"  Meeting ID : {meeting_id}")
        print(f"  Start      : {start}")
        print(f"  Duration   : {duration} min")

        recording_files = meeting.get("recording_files", [])
        if recording_files:
            print(f"  Files ({len(recording_files)}):")
            for f in recording_files:
                ftype = f.get("file_type", "?")
                fext = f.get("file_extension", "?")
                fsize = f.get("file_size", None)
                status = f.get("status", "?")
                rec_type = f.get("recording_type", "?")
                download_url = f.get("download_url", "N/A")
                play_url = f.get("play_url", "N/A")

                print(f"    [{ftype}/{fext}]  {rec_type}")
                print(f"      Size     : {format_size(fsize)}")
                print(f"      Status   : {status}")
                print(f"      Download : {download_url}")
                if play_url != "N/A":
                    print(f"      Play     : {play_url}")
        else:
            print("  Files: (none)")

        print()

    # Also dump the full raw JSON for reference
    print("=" * 60)
    print("=== Full Raw JSON Response ===")
    print("=" * 60)
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching Zoom access token...\n")
    token = get_access_token()

    print("Fetching cloud recordings...\n")
    data = list_recordings(token)

    print_recordings(data)
