"""不足11件をNotionに追加 + 既存レコードのYouTubeリンク修正"""

import json
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


def query_all_records():
    """既存レコードを全取得"""
    url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        r = requests.post(url, headers=HEADERS, json=body)
        r.raise_for_status()
        data = r.json()
        results.extend(data["results"])
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def get_title(page):
    """ページからタイトルを取得"""
    props = page.get("properties", {})
    title_prop = props.get("動画タイトル", {})
    title_items = title_prop.get("title", [])
    if title_items:
        return title_items[0].get("text", {}).get("content", "")
    return ""


def get_youtube_url(page):
    """ページからYouTubeリンクを取得"""
    props = page.get("properties", {})
    url_prop = props.get("YouTubeリンク", {})
    return url_prop.get("url", "")


def extract_video_id(url):
    """YouTubeリンクからvideo IDを抽出"""
    if not url:
        return ""
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", url)
    return m.group(1) if m else ""


def create_record(title, youtube_url, tag="マネタイズ"):
    """Notionにレコード作成"""
    video_id = extract_video_id(youtube_url)
    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    properties = {
        "動画タイトル": {
            "title": [{"text": {"content": title}}]
        },
        "YouTubeリンク": {
            "url": youtube_url
        },
        "タグ": {
            "multi_select": [{"name": tag}]
        },
    }

    body = {
        "parent": {"database_id": DB_ID},
        "properties": properties,
    }

    # サムネイルをカバー画像に
    if thumbnail_url:
        body["cover"] = {
            "type": "external",
            "external": {"url": thumbnail_url}
        }

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=body,
    )
    r.raise_for_status()
    page = r.json()
    page_id = page["id"]

    # YouTube埋め込みブロック追加
    if youtube_url:
        block_body = {
            "children": [
                {
                    "object": "block",
                    "type": "embed",
                    "embed": {"url": youtube_url},
                }
            ]
        }
        requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json=block_body,
        )

    return page_id


def update_youtube_url(page_id, new_url):
    """既存ページのYouTubeリンクを更新"""
    video_id = extract_video_id(new_url)
    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    body = {
        "properties": {
            "YouTubeリンク": {"url": new_url},
        },
    }
    if thumbnail_url:
        body["cover"] = {
            "type": "external",
            "external": {"url": thumbnail_url}
        }

    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json=body,
    )
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 60)
    print("Notion 動画一覧 DB 更新")
    print("=" * 60)

    # 1. 既存レコード取得
    print("\n1. 既存レコード取得...")
    existing = query_all_records()
    print(f"   既存: {len(existing)} 件")

    existing_map = {}
    for page in existing:
        title = get_title(page)
        yt = get_youtube_url(page)
        existing_map[title] = {"page_id": page["id"], "youtube_url": yt}
        print(f"   {title} → {yt}")

    # 2. 正しいYouTubeリンク（v2スクレイパーの直接アクセス結果）
    correct_links = {
        "1-2 _マネタイズマインドセット": "https://youtu.be/SLrb6TMoZ0Y",
        "1-2_マネタイズマインドセット": "https://youtu.be/SLrb6TMoZ0Y",
        "1-3_収益化までのステップ": "https://youtu.be/z71hYs5LhvE",
    }

    # 3. 既存レコードの修正
    print("\n2. 既存レコード修正...")
    for title, correct_url in correct_links.items():
        if title in existing_map:
            current_url = existing_map[title]["youtube_url"]
            if current_url != correct_url:
                page_id = existing_map[title]["page_id"]
                print(f"   修正: {title}")
                print(f"     旧: {current_url}")
                print(f"     新: {correct_url}")
                update_youtube_url(page_id, correct_url)
                time.sleep(0.5)
            else:
                print(f"   OK: {title} (リンク正常)")

    # 4. 不足レコード追加
    print("\n3. 不足レコード追加...")
    with open("assets/discord_past_posts.json", "r", encoding="utf-8") as f:
        missing = json.load(f)

    # 既存タイトルのセット（正規化して比較）
    existing_normalized = set()
    for t in existing_map:
        normalized = t.replace(" ", "").replace("_", "").replace("　", "")
        existing_normalized.add(normalized)

    added = 0
    for item in missing:
        title = item["title"]
        normalized = title.replace(" ", "").replace("_", "").replace("　", "")

        if normalized in existing_normalized:
            print(f"   スキップ (既存): {title}")
            continue

        youtube_url = item["youtube_links"][0] if item["youtube_links"] else ""
        if not youtube_url:
            print(f"   スキップ (リンクなし): {title}")
            continue

        print(f"   追加: {title} → {youtube_url}")
        page_id = create_record(title, youtube_url, item.get("tag", "マネタイズ"))
        print(f"     → page_id: {page_id}")
        added += 1
        time.sleep(0.5)

    # 5. 最終確認
    print(f"\n{'=' * 60}")
    print(f"完了: {added} 件追加")
    print(f"{'=' * 60}")

    # 最終レコード一覧
    print("\n最終レコード一覧:")
    final = query_all_records()
    for page in final:
        title = get_title(page)
        yt = get_youtube_url(page)
        print(f"  {title} → {yt}")
    print(f"\n合計: {len(final)} 件")


if __name__ == "__main__":
    main()
