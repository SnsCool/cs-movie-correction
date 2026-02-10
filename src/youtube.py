"""YouTube upload module using Data API v3.

Uploads videos and thumbnails to YouTube via resumable upload.

Environment variables required:
    YOUTUBE_CLIENT_ID     - OAuth 2.0 client ID
    YOUTUBE_CLIENT_SECRET - OAuth 2.0 client secret
    YOUTUBE_REFRESH_TOKEN - OAuth 2.0 refresh token
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

GOOGLE_OAUTH_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
)
YOUTUBE_THUMBNAIL_URL = (
    "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
)

CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


def get_access_token() -> str:
    """Exchange a refresh token for a YouTube OAuth access token.

    Posts to the Google OAuth endpoint with grant_type=refresh_token
    using YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and
    YOUTUBE_REFRESH_TOKEN.

    Returns:
        The access token string.

    Raises:
        EnvironmentError: If required environment variables are missing.
        requests.HTTPError: If the token request fails.
    """
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    missing = []
    if not client_id:
        missing.append("YOUTUBE_CLIENT_ID")
    if not client_secret:
        missing.append("YOUTUBE_CLIENT_SECRET")
    if not refresh_token:
        missing.append("YOUTUBE_REFRESH_TOKEN")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    logger.info("Requesting YouTube OAuth access token")

    response = requests.post(
        GOOGLE_OAUTH_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()

    token = response.json()["access_token"]
    logger.info("Successfully obtained YouTube access token")
    return token


def upload_video(
    file_path: str,
    title: str,
    description: str = "",
    privacy: str = "unlisted",
    category_id: str = "22",
) -> str:
    """Upload a video to YouTube using resumable upload.

    Initiates a resumable upload session, then sends the video file
    in 10 MB chunks.

    Args:
        file_path:    Path to the video file (MP4).
        title:        Video title.
        description:  Video description.
        privacy:      Privacy status (``unlisted``, ``private``, or ``public``).
        category_id:  YouTube category ID (default ``22`` = People & Blogs).

    Returns:
        The YouTube video ID of the uploaded video.

    Raises:
        FileNotFoundError: If the video file does not exist.
        requests.HTTPError: If any API request fails.
        RuntimeError: If the upload URL is not returned by the API.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    access_token = get_access_token()

    logger.info(
        "Initiating resumable upload for %s (%.2f MB)",
        title,
        file_size / (1024 * 1024),
    )

    # Step 1: Initiate the resumable upload session
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    init_response = requests.post(
        YOUTUBE_UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        },
        json=metadata,
        timeout=30,
    )
    init_response.raise_for_status()

    upload_url = init_response.headers.get("Location")
    if not upload_url:
        raise RuntimeError(
            "YouTube API did not return an upload URL in the Location header"
        )

    logger.info("Received upload URL, starting chunked upload")

    # Step 2: Upload the file in chunks
    with open(file_path, "rb") as f:
        bytes_sent = 0

        while bytes_sent < file_size:
            chunk = f.read(CHUNK_SIZE)
            chunk_length = len(chunk)
            range_end = bytes_sent + chunk_length - 1

            content_range = f"bytes {bytes_sent}-{range_end}/{file_size}"
            is_final_chunk = (range_end + 1) >= file_size

            logger.info(
                "Uploading chunk: %s (%.1f%%)",
                content_range,
                (range_end + 1) / file_size * 100,
            )

            upload_response = requests.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(chunk_length),
                    "Content-Range": content_range,
                },
                data=chunk,
                timeout=300,
            )

            if is_final_chunk:
                upload_response.raise_for_status()
            elif upload_response.status_code not in (200, 308):
                upload_response.raise_for_status()

            bytes_sent += chunk_length

    video_id = upload_response.json()["id"]
    logger.info("Upload complete: video_id=%s", video_id)
    return video_id


def set_thumbnail(video_id: str, image_path: str) -> bool:
    """Upload a custom thumbnail for a YouTube video.

    Args:
        video_id:   The YouTube video ID.
        image_path: Path to the thumbnail image file (JPEG or PNG).

    Returns:
        True if the thumbnail was set successfully.

    Raises:
        FileNotFoundError: If the image file does not exist.
        requests.HTTPError: If the API request fails.
    """
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Thumbnail file not found: {image_path}")

    access_token = get_access_token()

    logger.info(
        "Uploading thumbnail for video %s from %s", video_id, image_path
    )

    # Detect content type from extension
    ext = os.path.splitext(image_path)[1].lower()
    content_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    content_type = content_type_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = f.read()

    response = requests.post(
        YOUTUBE_THUMBNAIL_URL,
        params={"videoId": video_id},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
        },
        data=image_data,
        timeout=60,
    )
    response.raise_for_status()

    logger.info("Thumbnail set successfully for video %s", video_id)
    return True


def get_video_url(video_id: str) -> str:
    """Return the short YouTube URL for a video.

    Args:
        video_id: The YouTube video ID.

    Returns:
        The URL in the form ``https://youtu.be/{video_id}``.
    """
    return f"https://youtu.be/{video_id}"


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    import sys

    if len(sys.argv) < 3:
        print("Usage: python youtube.py <video_file> <title> [description]")
        sys.exit(1)

    video_file = sys.argv[1]
    video_title = sys.argv[2]
    video_description = sys.argv[3] if len(sys.argv) > 3 else ""

    vid = upload_video(video_file, video_title, video_description)
    url = get_video_url(vid)
    print(f"\nUploaded: {url}")
