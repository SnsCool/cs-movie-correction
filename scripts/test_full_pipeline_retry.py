"""フルパイプラインE2Eテスト: パターン1・2のみ再実行
前回パターン3は成功済み。修正後のthumbnail.pyでパターン1・2を再実行。
"""

import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import discord as discord_mod
import notion
import thumbnail
import trim
import youtube
import zoom

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline_retry")

TEST_RECORDS = [
    {
        "page_id": "306f3b0f-ba85-81af-8bb7-fb250a3e15ef",
        "name": "パターン1（2人対談）",
        "zoom_start": "2026-02-09T00:01:22Z",
    },
    {
        "page_id": "306f3b0f-ba85-81a2-8106-fa26712015f2",
        "name": "パターン2（スマホ）",
        "zoom_start": "2026-02-04T01:59:53Z",
    },
]


def fetch_notion_record(page_id):
    import requests
    headers = notion._headers()
    resp = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, timeout=30)
    resp.raise_for_status()
    return notion.parse_master_record(resp.json())


def find_zoom_recording(zoom_start):
    dt = datetime.fromisoformat(zoom_start.replace("Z", "+00:00"))
    from_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    recordings = zoom.list_recordings(from_date, to_date)
    for meeting in recordings:
        meeting_start = meeting.get("start_time", "")
        if not meeting_start:
            continue
        meeting_dt = datetime.fromisoformat(meeting_start.replace("Z", "+00:00"))
        if abs((meeting_dt - dt).total_seconds()) <= 1800:
            files = meeting.get("recording_files", [])
            if files:
                return {"topic": meeting.get("topic", ""), "file": files[0]}
    return None


def process_one(test_info, tmp_dir):
    page_id = test_info["page_id"]

    print(f"\n  1. Notionレコード取得...")
    record = fetch_notion_record(page_id)
    print(f"     タイトル: {record['title']}, パターン: {record['pattern']}")

    print(f"  2. Zoom録画検索...")
    zm = find_zoom_recording(test_info["zoom_start"])
    if not zm:
        print(f"     ❌ Zoom録画が見つかりません")
        return False
    print(f"     Topic: {zm['topic']}, Size: {zm['file']['file_size']/(1024*1024):.0f}MB")

    print(f"  3. ステータス → 処理中...")
    notion.update_status(page_id, "処理中")

    print(f"  4. Zoom録画ダウンロード中...")
    access_token = zoom.get_access_token()
    raw_path = os.path.join(tmp_dir, f"{page_id}_raw.mp4")
    zoom.download_recording(zm["file"]["download_url"], access_token, raw_path)
    print(f"     ✅ {os.path.getsize(raw_path)/(1024*1024):.1f} MB")

    print(f"  5. トリミング...")
    trimmed_path = os.path.join(tmp_dir, f"{page_id}_trimmed.mp4")
    trimmed_path = trim.auto_trim(raw_path, trimmed_path)
    print(f"     ✅ {os.path.getsize(trimmed_path)/(1024*1024):.1f} MB")

    print(f"  6. サムネイル生成...")
    thumbnail_path = thumbnail.generate_thumbnail(record, base_dir=str(PROJECT_ROOT))
    print(f"     ✅ {thumbnail_path}")

    print(f"  7. YouTubeアップロード...")
    video_id = youtube.upload_video(file_path=trimmed_path, title=record["title"])
    youtube_url = youtube.get_video_url(video_id)
    print(f"     ✅ {youtube_url}")

    print(f"  8. YouTubeサムネイル設定...")
    youtube.set_thumbnail(video_id, thumbnail_path)
    print(f"     ✅ 完了")

    print(f"  9. Discord通知...")
    notion_page_url = f"https://notion.so/{page_id.replace('-', '')}"
    discord_thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    try:
        discord_mod.send_notification(
            title=record["title"], youtube_url=youtube_url,
            thumbnail_url=discord_thumbnail,
            lecturer=record.get("lecturer_name", ""),
            category=record.get("category", ""),
            notion_url=notion_page_url,
            genre=record.get("genre", ""),
            thumbnail_text=record.get("thumbnail_text", ""),
            student_name=record.get("student_name", ""),
        )
        print(f"     ✅ 完了")
    except Exception as e:
        print(f"     ⚠️ 失敗（続行）: {e}")

    print(f"  10. 動画アーカイブ作成...")
    start_date = record.get("start_time", "")[:10]
    notion.create_video_record(
        title=record["title"], category=record.get("category", ""),
        date=start_date, lecturer=record.get("lecturer_name", ""),
        youtube_url=youtube_url, thumbnail_url=discord_thumbnail,
    )
    print(f"     ✅ 完了")

    print(f"  11. ステータス → 完了...")
    notion.update_status(page_id, "完了", youtube_url=youtube_url)
    print(f"     ✅ 完了 (YouTube: {youtube_url})")

    return True


def main():
    print("=" * 60)
    print("パターン1・2 フルパイプライン再実行")
    print("=" * 60)

    tmp_dir = tempfile.mkdtemp(prefix="cs_retry_")
    results = []

    try:
        for i, t in enumerate(TEST_RECORDS, 1):
            print(f"\n{'━' * 60}")
            print(f"[{i}/2] {t['name']}")
            print(f"━" * 60)
            try:
                ok = process_one(t, tmp_dir)
                results.append((t["name"], ok))
                if ok:
                    print(f"\n  🎉 {t['name']} → 完了!")
            except Exception as e:
                logger.exception(f"Error: {t['name']}")
                results.append((t["name"], False))
                print(f"\n  ❌ {t['name']} → 失敗: {e}")
                try:
                    notion.update_status(t["page_id"], "エラー", error_msg=str(e))
                except Exception:
                    pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print("結果サマリー")
    print(f"{'=' * 60}")
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    # パターン3の結果も再表示
    print(f"  ✅ パターン3（1on1） — 前回成功済み: https://youtu.be/_SNSCm6eAhA")

    all_pass = all(ok for _, ok in results)
    print(f"\n{'🎉 全パターン成功!' if all_pass else '⚠️ 一部失敗'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
