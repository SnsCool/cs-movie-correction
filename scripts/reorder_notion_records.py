"""Notionレコードを番号順に再作成（削除→逆順で作成→デフォルトで番号順表示）"""

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


def get_tags(page):
    tags = page.get("properties", {}).get("タグ", {}).get("multi_select", [])
    return [t["name"] for t in tags]


def archive_page(page_id):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"archived": True},
    )
    r.raise_for_status()


def create_record(title, youtube_url, number, tags):
    video_id = ""
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&\s]+)", youtube_url or "")
    if m:
        video_id = m.group(1)
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    body = {
        "parent": {"database_id": DB_ID},
        "properties": {
            "動画タイトル": {"title": [{"text": {"content": title}}]},
            "YouTubeリンク": {"url": youtube_url},
            "番号": {"number": number},
            "タグ": {"multi_select": [{"name": t} for t in tags]},
        },
    }
    if thumbnail:
        body["cover"] = {"type": "external", "external": {"url": thumbnail}}

    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=body)
    r.raise_for_status()
    page_id = r.json()["id"]

    # YouTube埋め込み
    if youtube_url:
        requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json={"children": [{"object": "block", "type": "embed", "embed": {"url": youtube_url}}]},
        )

    return page_id


def main():
    # 1. 全レコード取得
    pages = query_all()
    print(f"既存: {len(pages)} 件\n")

    # データ保存
    records = []
    for page in pages:
        records.append({
            "title": get_title(page),
            "url": get_url(page),
            "number": get_number(page),
            "tags": get_tags(page),
            "page_id": page["id"],
        })

    # 番号順ソート
    records.sort(key=lambda x: x["number"])

    print("ソート順:")
    for r in records:
        print(f"  {r['number']:3d} | {r['title']} → {r['url']}")

    # 2. 全レコード削除
    print(f"\n全 {len(records)} 件を削除中...")
    for r in records:
        archive_page(r["page_id"])
        time.sleep(0.3)
    print("  削除完了")

    # 3. 逆順で再作成（5-2から1-1へ。最後に作った1-1が一番上に来る）
    print(f"\n番号の大きい順に再作成中...")
    reversed_records = list(reversed(records))

    for r in reversed_records:
        page_id = create_record(r["title"], r["url"], r["number"], r["tags"])
        print(f"  作成: {r['number']:3d} | {r['title']}")
        time.sleep(0.5)

    # 4. 確認
    print(f"\n最終確認:")
    final = query_all()
    for page in final:
        title = get_title(page)
        num = get_number(page)
        url = get_url(page)
        print(f"  {num:3d} | {title} → {url}")

    print(f"\n完了！ {len(final)} 件（番号順で表示されます）")


if __name__ == "__main__":
    main()
