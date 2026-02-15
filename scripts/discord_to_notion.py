"""
抽出したDiscordデータをNotionの動画一覧DBに格納する。
既存レコードとの重複チェック付き。
"""

import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_VIDEO_DB_ID = "306f3b0f-ba85-81df-b1d5-c50fa215c62a"
BASE_URL = "https://api.notion.com/v1"


def headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def get_existing_youtube_ids() -> set[str]:
    """既存レコードのYouTube video IDsを取得"""
    resp = requests.post(
        f"{BASE_URL}/databases/{NOTION_VIDEO_DB_ID}/query",
        headers=headers(),
        json={},
        timeout=30,
    )
    resp.raise_for_status()
    ids = set()
    for page in resp.json().get("results", []):
        url = page["properties"].get("YouTubeリンク", {}).get("url", "")
        vid = extract_video_id(url)
        if vid:
            ids.add(vid)
    return ids


def extract_video_id(url: str) -> str:
    """YouTube URLからvideo IDを抽出"""
    if not url:
        return ""
    m = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=)([^&?\s]+)", url)
    return m.group(1) if m else ""


def create_record(
    title: str,
    tag: str,
    date: str | None,
    lecturer: str,
    youtube_url: str,
):
    """Notion動画一覧DBにレコードを作成"""
    vid = extract_video_id(youtube_url)
    thumb_url = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg" if vid else ""

    properties = {
        "動画タイトル": {"title": [{"text": {"content": title}}]},
        "タグ": {"multi_select": [{"name": tag}]},
        "YouTubeリンク": {"url": youtube_url},
    }

    if lecturer:
        properties["講師名"] = {"select": {"name": lecturer}}

    if date:
        properties["日付"] = {"date": {"start": date}}

    if thumb_url:
        properties["サムネイル"] = {
            "files": [
                {
                    "name": "thumbnail.png",
                    "type": "external",
                    "external": {"url": thumb_url},
                }
            ]
        }

    children = [
        {
            "object": "block",
            "type": "video",
            "video": {"type": "external", "external": {"url": youtube_url}},
        }
    ]

    payload = {
        "parent": {"database_id": NOTION_VIDEO_DB_ID},
        "properties": properties,
        "children": children,
    }

    if thumb_url:
        payload["cover"] = {
            "type": "external",
            "external": {"url": thumb_url},
        }

    resp = requests.post(
        f"{BASE_URL}/pages", headers=headers(), json=payload, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["id"]


# === All extracted data ===
ALL_RECORDS = [
    # 1on1アーカイブ (16件)
    {"title": "2026.1.15_しゅうへい講師×ごとうさえさん", "date": "2026-01-15", "lecturer": "しゅうへい", "tag": "1on1", "yt": "https://youtu.be/GEGZmJlxiS4"},
    {"title": "2026.1.17_陸講師×つかもとけんしさん", "date": "2026-01-17", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/uweXiwsjeZk"},
    {"title": "2026.1.20_しゅうへい講師×あんどうことみさん", "date": "2026-01-20", "lecturer": "しゅうへい", "tag": "1on1", "yt": "https://youtu.be/nV-gDZWTTH8"},
    {"title": "2026.1.21_みくぽん講師×えむさん", "date": "2026-01-21", "lecturer": "みくぽん", "tag": "1on1", "yt": "https://youtu.be/rmeY5LM5mZA"},
    {"title": "2026.1.22_陸講師×ゆちゃまるさん", "date": "2026-01-22", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/hgiGqbrT8b8"},
    {"title": "2026.1.22_陸講師×えりかさん", "date": "2026-01-22", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/h-j3YmfRr4A"},
    {"title": "2026.1.22_陸講師×れいなさん", "date": "2026-01-22", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/-JVK-Ot4HCk"},
    {"title": "2026.1.22_陸講師×ゆいさん", "date": "2026-01-22", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/2kfHtei8s_g"},
    {"title": "2026.1.22_陸講師×ゆりなさん", "date": "2026-01-22", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/sozVro5NukA"},
    {"title": "2026.1.28_陸講師×やんけさん", "date": "2026-01-28", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/cva2iVcLX34"},
    {"title": "2026.1.30_しゅうへい講師×きたじまあやなさん", "date": "2026-01-30", "lecturer": "しゅうへい", "tag": "1on1", "yt": "https://youtu.be/d_YStO8TJO4"},
    {"title": "2026.1.31_たっちー講師×たくみさん", "date": "2026-01-31", "lecturer": "たっちー", "tag": "1on1", "yt": "https://youtu.be/Ec_J1X2qggk"},
    {"title": "2026.1.31_じゅん講師×にしやまゆうなさん", "date": "2026-01-31", "lecturer": "じゅん", "tag": "1on1", "yt": "https://youtu.be/8iwWlRNcxtg"},
    {"title": "2026.2.3_しゅうへい講師×あんどうことみさん", "date": "2026-02-03", "lecturer": "しゅうへい", "tag": "1on1", "yt": "https://youtu.be/lWM35ZYZpgY"},
    {"title": "2026.2.9_陸講師×Kellyさん", "date": "2026-02-09", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/ioQD_fF7v-M"},
    {"title": "2026.2.9_陸講師×とりどりさん", "date": "2026-02-09", "lecturer": "陸", "tag": "1on1", "yt": "https://youtu.be/O7l9JlJsgOg"},
    # グルコンアーカイブ (12件)
    {"title": "2026.1.14 グルコン｜ちゃみ講師", "date": "2026-01-14", "lecturer": "ちゃみ", "tag": "グループコンサル", "yt": "https://youtu.be/6y5ZDTCCcNk"},
    {"title": "2026.1.15 講師対談｜陸講師×じゅん講師", "date": "2026-01-15", "lecturer": "陸", "tag": "グループコンサル", "yt": "https://youtu.be/fg9uWvVgkwc"},
    {"title": "2026.1.18 グルコン｜かりん講師", "date": "2026-01-18", "lecturer": "かりん", "tag": "グループコンサル", "yt": "https://youtu.be/tUHjQ94sdDI"},
    {"title": "2026.1.20 グルコン｜たっちー講師", "date": "2026-01-20", "lecturer": "たっちー", "tag": "グループコンサル", "yt": "https://youtu.be/NugZaEk3heA"},
    {"title": "2026.1.21 講師対談｜陸講師×みくぽん講師", "date": "2026-01-21", "lecturer": "陸", "tag": "グループコンサル", "yt": "https://youtu.be/3St6PdiIkRI"},
    {"title": "2026.1.22 グルコン｜しゅうへい講師", "date": "2026-01-22", "lecturer": "しゅうへい", "tag": "グループコンサル", "yt": "https://youtu.be/xGXy7R7Roc4"},
    {"title": "2026.1.27 講師対談｜陸講師×ちゃみ講師", "date": "2026-01-27", "lecturer": "陸", "tag": "グループコンサル", "yt": "https://youtu.be/l0wVu1AybvE"},
    {"title": "2026.1.29 グルコン｜じゅん講師", "date": "2026-01-29", "lecturer": "じゅん", "tag": "グループコンサル", "yt": "https://youtu.be/2-NOW7w8tyE"},
    {"title": "2026.2.1 グルコン｜かりん講師", "date": "2026-02-01", "lecturer": "かりん", "tag": "グループコンサル", "yt": "https://youtu.be/5TYjR9_xZQg"},
    {"title": "2026.2.3 グルコン｜じゅん講師", "date": "2026-02-03", "lecturer": "じゅん", "tag": "グループコンサル", "yt": "https://youtu.be/zIr7COCJSMk"},
    {"title": "2026.2.6 グルコン｜陸講師", "date": "2026-02-06", "lecturer": "陸", "tag": "グループコンサル", "yt": "https://youtu.be/uOFdhJxj5jg"},
    {"title": "2026.2.9 グルコン｜みくぽん講師", "date": "2026-02-09", "lecturer": "みくぽん", "tag": "グループコンサル", "yt": "https://youtu.be/swUvhiHpIgM"},
    # マネタイズ動画講義 (12件) - 日付なし、カリキュラム番号順
    {"title": "1-2 _マネタイズマインドセット", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/8DQPYTQnSfs"},
    {"title": "1-3_収益化までのステップ", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/gmOMRgJfLzM"},
    {"title": "1-4 _コンプライアンス", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/SKqzbWsZEUw"},
    {"title": "2-1_企業案件の全体像", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/BA2jbycOMEY"},
    {"title": "2-2_企業にアプローチする方法", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/Qpfz0jCcu0w"},
    {"title": "3-1_アフィリエイト基礎と仕組み理解", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/FqNVQWxVcZU"},
    {"title": "3-2_ASP登録から案件選定までの手順", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/YYRXLTPglvs"},
    {"title": "3-4_アフィリエイト：投稿編", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/zzV2Kzkj10E"},
    {"title": "3-5_アフィリエイト：ストーリーズ編", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/D2_9Y-wU6Bo"},
    {"title": "3-6_収益分析と改善サイクル", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/MFMMyNzTTU0"},
    {"title": "4-6_価格設計", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/Mh5Wh3tqVuI"},
    {"title": "4-8_個別相談・セールス", "date": None, "lecturer": "", "tag": "マネタイズ", "yt": "https://youtu.be/ABC5-SL7TZ0"},
]


def main():
    # 既存レコードの重複チェック
    existing_ids = get_existing_youtube_ids()
    print(f"既存レコード: {len(existing_ids)} 件")
    print(f"既存video IDs: {existing_ids}")

    # Sort by date
    ALL_RECORDS.sort(key=lambda x: x.get("date") or "9999-99-99")

    new_count = 0
    skip_count = 0

    for r in ALL_RECORDS:
        vid = extract_video_id(r["yt"])
        if vid in existing_ids:
            print(f"  SKIP (duplicate): {r['title'][:50]}")
            skip_count += 1
            continue

        print(f"  CREATE: {r.get('date') or 'no-date':10s} | {r['tag']:12s} | {r['title'][:50]}")
        try:
            page_id = create_record(
                title=r["title"],
                tag=r["tag"],
                date=r.get("date"),
                lecturer=r.get("lecturer", ""),
                youtube_url=r["yt"],
            )
            print(f"    → OK: {page_id}")
            new_count += 1
            time.sleep(0.4)  # Rate limit
        except Exception as e:
            print(f"    → ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"完了: 新規 {new_count} 件 / スキップ {skip_count} 件 / 合計 {len(ALL_RECORDS)} 件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
