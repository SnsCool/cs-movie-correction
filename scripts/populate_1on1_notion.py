"""1on1アーカイブのNotionページにDBを作成し、Discord動画を追加"""

import json
import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv("/Users/hatakiyoto/cs-movie-correction/.env")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
# マネタイズ講座Portal配下の1on1アーカイブページ
ONE_ON_ONE_PAGE_ID = "306f3b0f-ba85-8085-8fa6-d3f642d9dc49"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def clean_youtube_url(url):
    """YouTube URLからトラッキングパラメータや不要文字を除去"""
    url = url.rstrip("｜|")
    url = re.sub(r'\?si=[^&\s]+', '', url)
    return url


def extract_video_id(url):
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&?\s｜|]+)", url)
    return m.group(1) if m else ""


def parse_date(title):
    """タイトルから日付を抽出 (YYYY-MM-DD)"""
    # 複数の日付フォーマットに対応
    # 2026.2.12, 2026/1/13, 2025.10.16, 2025.10.12
    m = re.match(r"(\d{2,4})[./](\d{1,2})[./](\d{1,2})", title)
    if m:
        year = m.group(1)
        if len(year) == 2:
            year = "20" + year
        month = m.group(2).zfill(2)
        day = m.group(3).zfill(2)
        return f"{year}-{month}-{day}"
    return None


def parse_lecturer_and_student(title):
    """タイトルから講師名と生徒名を抽出"""
    # パターン: 日付_講師名×生徒名 or 日付｜講師名×生徒名
    # 区切り: _, ｜, |, 半角スペース, 全角スペース
    # まず日付部分を除去
    cleaned = re.sub(r"^\d{2,4}[./]\d{1,2}[./]\d{1,2}[_｜|\s　]*", "", title)
    # マネタイズ講座1on1 プレフィックスも除去
    cleaned = re.sub(r"^マネタイズ講座1on1", "", cleaned)

    # 講師×生徒 パターン
    m = re.search(r"(.+?講師)[×x](.+?)$", cleaned)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # 講師名+生徒名（×なし）
    m = re.search(r"(.+?講師)(.+?)$", cleaned)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return "", ""


def create_page():
    """ポータル配下に1on1アーカイブページを作成"""
    body = {
        "parent": {"type": "page_id", "page_id": PORTAL_PAGE_ID},
        "properties": {
            "title": [{"type": "text", "text": {"content": "1on1アーカイブ"}}]
        },
        "icon": {"type": "emoji", "emoji": "🎯"},
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=body)
    r.raise_for_status()
    page = r.json()
    print(f"ページ作成: {page['id']}")
    return page["id"]


def create_database(parent_page_id):
    """1on1アーカイブページにインラインDBを作成"""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": ""}}],
        "is_inline": True,
        "properties": {
            "動画タイトル": {"title": {}},
            "YouTubeリンク": {"url": {}},
            "講師名": {"select": {}},
            "生徒名": {"rich_text": {}},
            "日付": {"date": {}},
            "番号": {"number": {}},
            "サムネイル": {"files": {}},
        },
    }
    r = requests.post(
        "https://api.notion.com/v1/databases",
        headers=HEADERS,
        json=body,
    )
    r.raise_for_status()
    db = r.json()
    print(f"DB作成: {db['id']}")
    return db["id"]


def create_record(db_id, title, youtube_url, lecturer, student, date_str, number):
    video_id = extract_video_id(youtube_url) if youtube_url else ""
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    properties = {
        "動画タイトル": {"title": [{"text": {"content": title}}]},
        "番号": {"number": number},
    }

    if youtube_url:
        properties["YouTubeリンク"] = {"url": youtube_url}

    if lecturer:
        properties["講師名"] = {"select": {"name": lecturer}}

    if student:
        properties["生徒名"] = {"rich_text": [{"text": {"content": student}}]}

    if date_str:
        properties["日付"] = {"date": {"start": date_str}}

    if thumb_url:
        properties["サムネイル"] = {
            "files": [{"type": "external", "name": title[:95], "external": {"url": thumb_url}}]
        }

    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    if thumb_url:
        body["cover"] = {"type": "external", "external": {"url": thumb_url}}

    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=body)
    r.raise_for_status()
    page_id = r.json()["id"]

    # YouTube埋め込みブロック
    if youtube_url:
        requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json={"children": [{"object": "block", "type": "embed", "embed": {"url": youtube_url}}]},
        )

    return page_id


def main():
    # データ読み込み
    with open("assets/discord_channel_1416428648482996337.json", "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Discord動画: {len(records)} 件")

    # 日付でソート（古い順）
    def sort_key(r):
        d = parse_date(r["title"])
        return d or "9999-99-99"

    records.sort(key=sort_key)

    # 既存ページにDB作成（マネタイズ講座Portal配下の1on1アーカイブ）
    page_id = ONE_ON_ONE_PAGE_ID
    print(f"\n既存ページ使用: {page_id}")
    print("DB作成中...")
    db_id = create_database(page_id)

    # 逆順（新しい順）で作成 → デフォルト表示で古い順が上
    print(f"\n{len(records)} 件を追加中...\n")

    for idx, record in enumerate(reversed(records)):
        title = record["title"]
        yt_links = record["youtube_links"]
        yt_url = clean_youtube_url(yt_links[0]) if yt_links else ""

        lecturer, student = parse_lecturer_and_student(title)
        date_str = parse_date(title)
        number = len(records) - idx  # 古い順で1から

        print(f"  {number:3d} | {date_str or '????-??-??'} | {lecturer or '?'} × {student or '?'} → {yt_url[:40] if yt_url else 'NO LINK'}")

        try:
            create_record(db_id, title, yt_url, lecturer, student, date_str, number)
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.4)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(records)} 件をNotionに追加")
    print(f"ページ ID: {page_id}")
    print(f"DB ID: {db_id}")
    print(f"ページ: https://notion.so/{page_id.replace('-', '')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
