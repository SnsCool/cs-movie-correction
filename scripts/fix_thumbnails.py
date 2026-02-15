"""全レコードの「サムネイル」filesプロパティにYouTubeサムネ画像を設定"""

import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv("/Users/hatakiyoto/cs-movie-correction/.env")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = "306f3b0f-ba85-81df-b1d5-c50fa215c62a"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def query_all():
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={"page_size": 100},
    )
    r.raise_for_status()
    return r.json()["results"]


def get_title(page):
    items = page.get("properties", {}).get("動画タイトル", {}).get("title", [])
    return items[0]["text"]["content"] if items else ""


def get_url(page):
    return page.get("properties", {}).get("YouTubeリンク", {}).get("url", "")


def get_number(page):
    return page.get("properties", {}).get("番号", {}).get("number", 999)


def update_thumbnail(page_id, thumbnail_url, title):
    body = {
        "properties": {
            "サムネイル": {
                "files": [
                    {
                        "type": "external",
                        "name": title,
                        "external": {"url": thumbnail_url},
                    }
                ]
            }
        }
    }
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json=body,
    )
    r.raise_for_status()


def main():
    pages = query_all()
    print(f"全 {len(pages)} 件のサムネイル設定\n")

    updated = 0
    for page in pages:
        title = get_title(page)
        yt_url = get_url(page)
        num = get_number(page)
        page_id = page["id"]

        m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", yt_url or "")
        if not m:
            print(f"  {num:3d} | {title} → スキップ（YouTubeリンクなし）")
            continue

        vid = m.group(1)
        thumbnail_url = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"

        print(f"  {num:3d} | {title} → {thumbnail_url}")
        update_thumbnail(page_id, thumbnail_url, title)
        updated += 1
        time.sleep(0.3)

    print(f"\n完了: {updated} 件のサムネイル設定済み")


if __name__ == "__main__":
    main()
