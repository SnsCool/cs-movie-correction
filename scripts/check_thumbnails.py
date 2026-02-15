"""サムネイルが表示されない原因を調査"""

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


def main():
    pages = query_all()

    print("=== サムネイル診断 ===\n")

    for page in pages[:3]:  # 最初の3件を詳細チェック
        title = get_title(page)
        yt_url = get_url(page)
        cover = page.get("cover")
        thumbnail_prop = page.get("properties", {}).get("サムネイル", {})

        print(f"--- {title} ---")
        print(f"  YouTubeリンク: {yt_url}")
        print(f"  カバー画像: {cover}")
        print(f"  サムネイルprop: {thumbnail_prop}")

        # YouTube video IDを抽出
        m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", yt_url or "")
        if m:
            vid = m.group(1)
            # maxresdefaultが存在するかチェック
            for size in ["maxresdefault", "hqdefault", "mqdefault"]:
                url = f"https://i.ytimg.com/vi/{vid}/{size}.jpg"
                r = requests.head(url, timeout=5)
                status = r.status_code
                print(f"  {size}.jpg: HTTP {status} {'OK' if status == 200 else 'NG'}")
        print()

    # DB スキーマ確認
    print("=== DB スキーマ ===")
    r = requests.get(f"https://api.notion.com/v1/databases/{DB_ID}", headers=HEADERS)
    r.raise_for_status()
    db = r.json()
    for prop_name, prop_val in db["properties"].items():
        print(f"  {prop_name}: {prop_val['type']}")


if __name__ == "__main__":
    main()
