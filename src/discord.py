"""Discord webhook notification module.

Sends rich embed messages to a Discord channel via webhook.
Designed to be non-blocking: failures are logged but never raised.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)


def _build_embed(
    title: str,
    youtube_url: str,
    thumbnail_url: str,
    lecturer: str,
    category: str,
) -> dict:
    """Build a Discord embed object.

    Args:
        title: Video title used as the embed description.
        youtube_url: YouTube video URL used as the embed link.
        thumbnail_url: Thumbnail image URL.
        lecturer: Lecturer / instructor name.
        category: Content category label.

    Returns:
        A dict representing a single Discord embed object.
    """
    embed: dict = {
        "title": "新しい動画がアップロードされました",
        "description": title,
        "url": youtube_url,
        "color": 5814783,
        "fields": [
            {"name": "講師", "value": lecturer or "未設定", "inline": True},
            {"name": "種別", "value": category or "未設定", "inline": True},
        ],
    }

    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    return embed


def send_notification(
    title: str,
    youtube_url: str,
    thumbnail_url: str = "",
    lecturer: str = "",
    category: str = "",
) -> bool:
    """Send a rich embed notification to Discord via webhook.

    This function is intentionally safe — it will **never** raise an
    exception.  Any failure (missing env var, network error, non-2xx
    response) is logged and ``False`` is returned so the rest of the
    pipeline can continue.

    Args:
        title: Video title.
        youtube_url: YouTube video URL.
        thumbnail_url: Optional thumbnail image URL.
        lecturer: Optional lecturer / instructor name.
        category: Optional content category.

    Returns:
        ``True`` if the webhook request succeeded (HTTP 2xx),
        ``False`` otherwise.
    """
    try:
        webhook_url: str = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning(
                "DISCORD_WEBHOOK_URL is not set or empty. "
                "Skipping Discord notification."
            )
            return False

        embed = _build_embed(
            title=title,
            youtube_url=youtube_url,
            thumbnail_url=thumbnail_url,
            lecturer=lecturer,
            category=category,
        )

        payload: dict = {"embeds": [embed]}

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
        )

        if response.ok:
            logger.info("Discord notification sent successfully for: %s", title)
            return True

        logger.error(
            "Discord webhook returned HTTP %d: %s",
            response.status_code,
            response.text,
        )
        return False

    except Exception:
        logger.exception("Failed to send Discord notification for: %s", title)
        return False
