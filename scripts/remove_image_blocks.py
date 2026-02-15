"""ページ内の画像ブロックを削除し、YouTube埋め込みだけを残す"""

import os
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


def get_children(page_id):
    r = requests.get(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()["results"]


def delete_block(block_id):
    r = requests.delete(f"https://api.notion.com/v1/blocks/{block_id}", headers=HEADERS)
    r.raise_for_status()


def main():
    pages = query_all()
    print(f"全 {len(pages)} 件の画像ブロックを削除\n")

    removed = 0
    for page in pages:
        title = get_title(page)
        page_id = page["id"]

        children = get_children(page_id)
        for child in children:
            if child["type"] == "image":
                print(f"  削除: {title} → image block")
                delete_block(child["id"])
                removed += 1
                time.sleep(0.3)

    print(f"\n完了: {removed} 件の画像ブロック削除")
    print(f"各ページにはYouTube埋め込みのみ残っています")
    print(f"\nギャラリービューのサムネイル表示:")
    print(f"  設定 → レイアウト → カードプレビュー → 「ページカバー画像」を選択")


if __name__ == "__main__":
    main()
