"""Notion動画一覧DBに「番号」プロパティを追加して番号順ソート可能にする"""

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


def add_number_property():
    """DBに「番号」numberプロパティを追加"""
    r = requests.patch(
        f"https://api.notion.com/v1/databases/{DB_ID}",
        headers=HEADERS,
        json={
            "properties": {
                "番号": {"number": {}}
            }
        },
    )
    r.raise_for_status()
    print("「番号」プロパティ追加完了")


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


def title_to_sort_number(title):
    """タイトルからソート番号を算出 (例: 1-1→101, 4-8→408, 5-2→502)"""
    m = re.match(r"(\d+)-(\d+)", title)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2))
        return major * 100 + minor
    return 999


def update_number(page_id, number):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"properties": {"番号": {"number": number}}},
    )
    r.raise_for_status()


def main():
    # 1. プロパティ追加
    add_number_property()

    # 2. 全レコード取得
    pages = query_all()
    print(f"\n全 {len(pages)} 件を更新中...\n")

    # 3. 各レコードに番号を設定
    records = []
    for page in pages:
        title = get_title(page)
        num = title_to_sort_number(title)
        records.append((num, title, page["id"]))

    records.sort(key=lambda x: x[0])

    for num, title, page_id in records:
        print(f"  {num:3d} | {title}")
        update_number(page_id, num)

    print(f"\n完了！Notionで「番号」列の昇順ソートで番号順に表示されます。")


if __name__ == "__main__":
    main()
