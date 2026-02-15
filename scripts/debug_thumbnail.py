"""サムネイルが表示されない原因を特定

1. ytimg.comのURLがNotionで使えるか確認
2. 別の画像URLで1件テストして比較
"""

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


def query_first():
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={"page_size": 1},
    )
    r.raise_for_status()
    return r.json()["results"][0]


def main():
    page = query_first()
    page_id = page["id"]
    title_items = page.get("properties", {}).get("動画タイトル", {}).get("title", [])
    title = title_items[0]["text"]["content"] if title_items else ""

    print(f"テスト対象: {title} (page_id: {page_id})")

    # 現在の状態
    cover = page.get("cover")
    thumbnail = page.get("properties", {}).get("サムネイル", {})
    print(f"\n現在のカバー: {cover}")
    print(f"現在のサムネイル: {thumbnail}")

    # YouTube thumbnail URLの確認
    yt_url = page.get("properties", {}).get("YouTubeリンク", {}).get("url", "")
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", yt_url or "")
    if m:
        vid = m.group(1)
        yt_thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"

        # URLのContent-TypeとContent-Length確認
        r = requests.head(yt_thumb, timeout=5, allow_redirects=True)
        print(f"\nYouTube thumbnail URL: {yt_thumb}")
        print(f"  Status: {r.status_code}")
        print(f"  Content-Type: {r.headers.get('Content-Type')}")
        print(f"  Content-Length: {r.headers.get('Content-Length')}")

        # hqdefaultも確認
        hq_thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        r2 = requests.head(hq_thumb, timeout=5, allow_redirects=True)
        print(f"\nhqdefault URL: {hq_thumb}")
        print(f"  Status: {r2.status_code}")
        print(f"  Content-Type: {r2.headers.get('Content-Type')}")
        print(f"  Content-Length: {r2.headers.get('Content-Length')}")

    # テスト: Notionが確実に表示できる画像URL（Wikipedia等）で試す
    test_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/YouTube_social_white_square_%282017%29.svg/240px-YouTube_social_white_square_%282017%29.svg.png"
    print(f"\nテスト画像をサムネイルに設定: {test_url}")

    body = {
        "properties": {
            "サムネイル": {
                "files": [
                    {
                        "type": "external",
                        "name": "test_thumbnail",
                        "external": {"url": test_url},
                    }
                ]
            }
        },
        "cover": {
            "type": "external",
            "external": {"url": test_url},
        }
    }
    r = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS, json=body)
    print(f"  更新結果: {r.status_code}")

    if r.status_code == 200:
        print(f"\nテスト画像を設定しました。Notionで表示されるか確認してください。")
        print(f"表示されれば → ytimg.comがNotionでブロックされている")
        print(f"表示されなければ → ギャラリービューの設定問題")


if __name__ == "__main__":
    main()
