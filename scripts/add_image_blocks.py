"""各ページの先頭にYouTubeサムネイルの画像ブロックを追加

ギャラリービューの「ページコンテンツ」プレビューで表示されるようにする
"""

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


def get_children(page_id):
    """ページの子ブロックを取得"""
    r = requests.get(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()["results"]


def delete_block(block_id):
    r = requests.delete(f"https://api.notion.com/v1/blocks/{block_id}", headers=HEADERS)
    r.raise_for_status()


def prepend_image_block(page_id, image_url, youtube_url):
    """ページの先頭に画像ブロックを追加し、その後にembed"""
    # まず既存の子ブロックを削除
    children = get_children(page_id)
    for child in children:
        delete_block(child["id"])
        time.sleep(0.2)

    # 画像ブロック + embed を追加
    blocks = [
        {
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": image_url},
            },
        },
        {
            "object": "block",
            "type": "embed",
            "embed": {"url": youtube_url},
        },
    ]

    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=HEADERS,
        json={"children": blocks},
    )
    r.raise_for_status()


def main():
    pages = query_all()
    print(f"全 {len(pages)} 件に画像ブロック追加\n")

    for page in pages:
        title = get_title(page)
        num = get_number(page)
        yt_url = get_url(page)
        page_id = page["id"]

        m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", yt_url or "")
        if not m:
            print(f"  {num:3d} | {title} → スキップ")
            continue

        vid = m.group(1)
        thumb_url = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

        print(f"  {num:3d} | {title} → 画像ブロック追加")
        prepend_image_block(page_id, thumb_url, yt_url)
        time.sleep(0.5)

    print(f"\n完了！")
    print(f"Notionのギャラリービューで:")
    print(f"  設定 → レイアウト → カードプレビュー → 「ページコンテンツ」を選択")


if __name__ == "__main__":
    main()
