"""フルパイプラインE2Eテスト: 3パターン全て
Zoom録画ダウンロード → トリミング → サムネ生成 → YouTube限定公開 → Discord通知 → Notion更新

テスト用に作成済みの3つのNotionレコードに対して実行。
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
logger = logging.getLogger("full_pipeline_test")

# テストで作成済みのNotionレコード
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
    {
        "page_id": "306f3b0f-ba85-8139-8857-cbff7db1cda3",
        "name": "パターン3（1on1）",
        "zoom_start": "2026-01-29T14:00:30Z",
    },
]


def fetch_notion_record(page_id: str) -> dict:
    """Notion APIからレコードを直接取得してパース"""
    import requests
    headers = notion._headers()
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return notion.parse_master_record(resp.json())


def find_zoom_recording(zoom_start: str) -> dict | None:
    """指定日時前後のZoom録画を検索"""
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
                return {
                    "topic": meeting.get("topic", ""),
                    "file": files[0],
                }
    return None


def process_record(test_info: dict, tmp_dir: str) -> dict:
    """1件のレコードをフルパイプラインで処理"""
    page_id = test_info["page_id"]
    result = {"name": test_info["name"], "steps": {}}

    try:
        # Step 1: Notionからレコード取得
        print(f"  1️⃣  Notionレコード取得...")
        record = fetch_notion_record(page_id)
        result["steps"]["notion_fetch"] = True
        print(f"     タイトル: {record['title']}")
        print(f"     パターン: {record['pattern']}")
        print(f"     ステータス: {record['status']}")

        # Step 2: Zoom録画検索
        print(f"  2️⃣  Zoom録画検索...")
        zoom_match = find_zoom_recording(test_info["zoom_start"])
        if not zoom_match:
            print(f"     ❌ マッチするZoom録画が見つかりません")
            result["steps"]["zoom_match"] = False
            return result
        result["steps"]["zoom_match"] = True
        print(f"     Topic: {zoom_match['topic']}")
        file_size_mb = zoom_match['file']['file_size'] / (1024 * 1024)
        print(f"     サイズ: {file_size_mb:.1f} MB")

        # Step 3: ステータス更新 → 処理中
        print(f"  3️⃣  ステータス → 処理中...")
        notion.update_status(page_id, "処理中")
        result["steps"]["status_processing"] = True

        # Step 4: Zoom録画ダウンロード
        print(f"  4️⃣  Zoom録画ダウンロード中... ({file_size_mb:.0f} MB)")
        download_url = zoom_match["file"]["download_url"]
        access_token = zoom.get_access_token()
        raw_path = os.path.join(tmp_dir, f"{page_id}_raw.mp4")
        zoom.download_recording(download_url, access_token, raw_path)
        result["steps"]["download"] = True
        print(f"     ✅ ダウンロード完了: {os.path.getsize(raw_path)/(1024*1024):.1f} MB")

        # Step 5: トリミング
        print(f"  5️⃣  無音トリミング中...")
        trimmed_path = os.path.join(tmp_dir, f"{page_id}_trimmed.mp4")
        trimmed_path = trim.auto_trim(raw_path, trimmed_path)
        result["steps"]["trim"] = True
        print(f"     ✅ トリミング完了: {os.path.getsize(trimmed_path)/(1024*1024):.1f} MB")

        # Step 6: サムネイル生成
        print(f"  6️⃣  サムネイル生成中...")
        thumbnail_path = thumbnail.generate_thumbnail(
            record, base_dir=str(PROJECT_ROOT)
        )
        result["steps"]["thumbnail"] = True
        print(f"     ✅ サムネイル生成完了: {thumbnail_path}")

        # Step 7: YouTube アップロード
        print(f"  7️⃣  YouTubeアップロード中...")
        video_id = youtube.upload_video(
            file_path=trimmed_path,
            title=record["title"],
            description="",
        )
        youtube_url = youtube.get_video_url(video_id)
        result["steps"]["youtube_upload"] = True
        result["youtube_url"] = youtube_url
        print(f"     ✅ YouTube: {youtube_url}")

        # Step 8: YouTubeサムネイル設定
        print(f"  8️⃣  YouTubeサムネイル設定...")
        youtube.set_thumbnail(video_id, thumbnail_path)
        result["steps"]["youtube_thumbnail"] = True
        print(f"     ✅ サムネイル設定完了")

        # Step 9: Discord通知
        print(f"  9️⃣  Discord通知...")
        notion_page_url = f"https://notion.so/{page_id.replace('-', '')}"
        discord_thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        try:
            discord_mod.send_notification(
                title=record["title"],
                youtube_url=youtube_url,
                thumbnail_url=discord_thumbnail_url,
                lecturer=record.get("lecturer_name", ""),
                category=record.get("category", ""),
                notion_url=notion_page_url,
                genre=record.get("genre", ""),
                thumbnail_text=record.get("thumbnail_text", ""),
                student_name=record.get("student_name", ""),
            )
            result["steps"]["discord"] = True
            print(f"     ✅ Discord通知完了")
        except Exception as e:
            result["steps"]["discord"] = False
            print(f"     ⚠️  Discord通知失敗（続行）: {e}")

        # Step 10: 動画アーカイブ作成
        print(f"  🔟  動画アーカイブ作成...")
        start_date = record.get("start_time", "")[:10]
        archive_thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        notion.create_video_record(
            title=record["title"],
            category=record.get("category", ""),
            date=start_date,
            lecturer=record.get("lecturer_name", ""),
            youtube_url=youtube_url,
            thumbnail_url=archive_thumbnail_url,
        )
        result["steps"]["video_archive"] = True
        print(f"     ✅ 動画アーカイブ作成完了")

        # Step 11: ステータス → 完了（YouTube URL付き）
        print(f"  1️⃣1️⃣  ステータス → 完了...")
        notion.update_status(page_id, "完了", youtube_url=youtube_url)
        result["steps"]["status_complete"] = True
        print(f"     ✅ ステータス完了、YouTube URL設定済み")

        result["success"] = True

    except Exception as e:
        logger.exception(f"Error processing {test_info['name']}")
        result["success"] = False
        result["error"] = str(e)
        # エラー時はNotionステータスを更新
        try:
            notion.update_status(page_id, "エラー", error_msg=str(e))
        except Exception:
            pass

    return result


def main():
    print("=" * 70)
    print("フルパイプライン E2Eテスト（3パターン）")
    print("Zoom → トリミング → サムネ → YouTube → Discord → Notion")
    print("=" * 70)

    tmp_dir = tempfile.mkdtemp(prefix="cs_pipeline_test_")
    print(f"\n一時ディレクトリ: {tmp_dir}")

    results = []

    try:
        for i, test_info in enumerate(TEST_RECORDS, 1):
            print(f"\n{'━' * 70}")
            print(f"[{i}/3] {test_info['name']}")
            print(f"  Page ID: {test_info['page_id']}")
            print(f"  Zoom開始: {test_info['zoom_start']}")
            print(f"{'━' * 70}")

            result = process_record(test_info, tmp_dir)
            results.append(result)

            if result.get("success"):
                print(f"\n  🎉 {test_info['name']} → 完了!")
            else:
                print(f"\n  ❌ {test_info['name']} → 失敗: {result.get('error', 'unknown')}")

    finally:
        print(f"\n一時ファイル削除中: {tmp_dir}")
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # サマリー
    print(f"\n{'=' * 70}")
    print("テスト結果サマリー")
    print(f"{'=' * 70}")

    all_pass = True
    for r in results:
        icon = "✅" if r.get("success") else "❌"
        yt = r.get("youtube_url", "N/A")
        print(f"  {icon} {r['name']}")
        if r.get("success"):
            print(f"     YouTube: {yt}")
            notion_url = f"https://notion.so/{[t for t in TEST_RECORDS if t['name'] == r['name']][0]['page_id'].replace('-', '')}"
            print(f"     Notion:  {notion_url}")
        else:
            all_pass = False
            print(f"     エラー: {r.get('error', 'unknown')}")
            print(f"     完了ステップ: {[k for k,v in r.get('steps', {}).items() if v]}")

    print()
    if all_pass:
        print("🎉🎉🎉 全3パターン フルパイプライン PASS! 🎉🎉🎉")
    else:
        print("⚠️  一部パイプライン失敗")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
