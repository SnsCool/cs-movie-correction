"""1-2と1-3のYouTubeリンクを修正"""

import os
import re
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
    url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
    r = requests.post(url, headers=HEADERS, json={"page_size": 100})
    r.raise_for_status()
    return r.json()["results"]


def get_title(page):
    title_items = page.get("properties", {}).get("動画タイトル", {}).get("title", [])
    return title_items[0]["text"]["content"] if title_items else ""


def get_url(page):
    return page.get("properties", {}).get("YouTubeリンク", {}).get("url", "")


def update_url(page_id, new_url):
    video_id = ""
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", new_url)
    if m:
        video_id = m.group(1)
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    body = {
        "properties": {
            "YouTubeリンク": {"url": new_url},
        },
    }
    if thumbnail:
        body["cover"] = {"type": "external", "external": {"url": thumbnail}}

    r = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS, json=body)
    r.raise_for_status()
    print(f"  Updated: {page_id}")


def main():
    pages = query_all()

    # 修正対象を特定
    corrections = {
        "1-2": "https://youtu.be/SLrb6TMoZ0Y",
        "1-3": "https://youtu.be/z71hYs5LhvE",
    }

    for page in pages:
        title = get_title(page)
        current_url = get_url(page)
        page_id = page["id"]

        for prefix, correct_url in corrections.items():
            if title.startswith(prefix):
                if current_url != correct_url:
                    print(f"\n修正: {title}")
                    print(f"  旧: {current_url}")
                    print(f"  新: {correct_url}")
                    update_url(page_id, correct_url)
                else:
                    print(f"\nOK: {title} (リンク正常)")

    # 最終確認 - 重複チェック
    print("\n--- 最終重複チェック ---")
    pages = query_all()
    url_map = {}
    for page in pages:
        title = get_title(page)
        yt = get_url(page)
        if yt in url_map:
            print(f"重複: {yt}")
            print(f"  → {url_map[yt]}")
            print(f"  → {title}")
        else:
            url_map[yt] = title

    if not any(yt for yt in url_map if list(url_map.values()).count(url_map[yt]) > 1):
        print("重複なし!")

    print(f"\n合計: {len(pages)} 件")


if __name__ == "__main__":
    main()
