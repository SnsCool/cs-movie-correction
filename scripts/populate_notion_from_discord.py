"""Notion 動画一覧DBをDiscordデータで再構築

1. 既存レコードを全削除（アーカイブ）
2. discord_extracted.json + discord_remaining.json からレコード作成
"""

import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import requests
import notion

DB_ID = "306f3b0f-ba85-81df-b1d5-c50fa215c62a"

# タグ名マッピング
TAG_MAP = {
    "1on1": "1on1",
    "グループコンサル": "グループコンサル",
    "マネタイズ": "マネタイズ",
}


def get_all_records():
    """DB内の全レコードIDを取得"""
    headers = notion._headers()
    all_ids = []
    has_more = True
    start_cursor = None

    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        resp = requests.post(
            f"https://api.notion.com/v1/databases/{DB_ID}/query",
            headers=headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        for r in data.get("results", []):
            title_prop = r.get("properties", {}).get("動画タイトル", {}).get("title", [])
            title = title_prop[0]["plain_text"] if title_prop else "(untitled)"
            all_ids.append({"id": r["id"], "title": title})

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return all_ids


def archive_record(page_id):
    """レコードをアーカイブ（削除）"""
    headers = notion._headers()
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers,
        json={"archived": True},
        timeout=30
    )
    resp.raise_for_status()


def clean_youtube_url(url):
    """YouTube URLからトラッキングパラメータを除去し、短縮URLに統一"""
    # youtu.be/XXX?si=YYY → youtu.be/XXX
    url = re.sub(r'\?si=[^&]+', '', url)
    # www.youtube.com/watch?v=XXX → youtu.be/XXX
    m = re.match(r'https?://(?:www\.)?youtube\.com/watch\?v=([^&]+)', url)
    if m:
        return f"https://youtu.be/{m.group(1)}"
    return url


def determine_tag(entry):
    """エントリーからタグを決定"""
    title = entry.get("title", "")
    tag = entry.get("tag", "")
    channel = entry.get("channel", "")

    # 講師対談の判定
    if "講師対談" in title or "対談" in title:
        return "講師対談"

    return TAG_MAP.get(tag, tag)


def determine_lecturer(entry):
    """講師名をselectオプションに合わせる"""
    lecturer = entry.get("lecturer", "")
    # selectオプション: 陸, たっちー, しゅうへい, はなこ, ちゃみ, かりん, じゅん, みくぽん
    valid = {"陸", "たっちー", "しゅうへい", "はなこ", "ちゃみ", "かりん", "じゅん", "みくぽん"}
    if lecturer in valid:
        return lecturer
    return ""


def create_video_record(entry):
    """Discordエントリーから動画一覧レコードを作成"""
    headers = notion._headers()

    title = entry["title"]
    youtube_links = entry.get("youtube_links", [])
    youtube_url = clean_youtube_url(youtube_links[0]) if youtube_links else ""
    date = entry.get("date")
    tag = determine_tag(entry)
    lecturer = determine_lecturer(entry)

    # YouTube Video IDからサムネイルURLを生成
    thumbnail_url = ""
    if youtube_url:
        vid_match = re.search(r'youtu\.be/([^?&]+)', youtube_url)
        if vid_match:
            vid_id = vid_match.group(1)
            thumbnail_url = f"https://i.ytimg.com/vi/{vid_id}/maxresdefault.jpg"

    properties = {
        "動画タイトル": {"title": [{"text": {"content": title}}]},
    }

    if youtube_url:
        properties["YouTubeリンク"] = {"url": youtube_url}

    if date:
        properties["日付"] = {"date": {"start": date}}

    if tag:
        properties["タグ"] = {"multi_select": [{"name": tag}]}

    if lecturer:
        properties["講師名"] = {"select": {"name": lecturer}}

    if thumbnail_url:
        properties["サムネイル"] = {
            "files": [{"name": title, "type": "external", "external": {"url": thumbnail_url}}]
        }

    payload = {
        "parent": {"database_id": DB_ID},
        "properties": properties,
    }

    # YouTube embed as page content
    children = []
    if youtube_url:
        children.append({
            "object": "block",
            "type": "embed",
            "embed": {"url": youtube_url}
        })
    if children:
        payload["children"] = children

    # カバー画像
    if thumbnail_url:
        payload["cover"] = {
            "type": "external",
            "external": {"url": thumbnail_url}
        }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["id"]


def main():
    print("=" * 60)
    print("Notion 動画一覧DB再構築")
    print("=" * 60)

    # Step 1: 既存レコード全削除
    print("\n[Step 1] 既存レコード削除")
    records = get_all_records()
    print(f"  削除対象: {len(records)}件")

    for i, rec in enumerate(records, 1):
        archive_record(rec["id"])
        if i % 10 == 0:
            print(f"  ... {i}/{len(records)} 削除完了")
            time.sleep(0.5)  # Rate limit対策
    print(f"  ✅ {len(records)}件 削除完了")

    # Step 2: Discordデータ読み込み
    print("\n[Step 2] Discordデータ読み込み")
    extracted = json.loads((PROJECT_ROOT / "assets" / "discord_extracted.json").read_text(encoding="utf-8"))
    remaining = json.loads((PROJECT_ROOT / "assets" / "discord_remaining.json").read_text(encoding="utf-8"))

    all_entries = extracted + remaining
    print(f"  1on1アーカイブ: {len(extracted)}件")
    print(f"  グルコン + マネタイズ: {len(remaining)}件")
    print(f"  合計: {len(all_entries)}件")

    # Step 3: レコード作成
    print("\n[Step 3] Notionレコード作成")
    created = 0
    errors = 0

    for i, entry in enumerate(all_entries, 1):
        try:
            page_id = create_video_record(entry)
            tag = determine_tag(entry)
            yt = entry.get("youtube_links", [""])[0][:40] if entry.get("youtube_links") else ""
            print(f"  {i:2d}. ✅ {entry['title'][:40]}")
            print(f"      タグ={tag} 講師={entry.get('lecturer', '')} YT={yt}...")
            created += 1

            # Rate limit対策
            if i % 3 == 0:
                time.sleep(0.3)
        except Exception as e:
            print(f"  {i:2d}. ❌ {entry['title']}: {e}")
            errors += 1

    # サマリー
    print(f"\n{'=' * 60}")
    print("完了サマリー")
    print(f"{'=' * 60}")
    print(f"  削除: {len(records)}件")
    print(f"  作成: {created}件 (エラー: {errors}件)")
    print(f"  Notion: https://www.notion.so/301f3b0fba85801ebbbae30bda6ee7aa")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
