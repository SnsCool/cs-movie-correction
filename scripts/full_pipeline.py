"""
フルパイプライン実行スクリプト
Zoom録画取得 → Notionマスター登録 → ダウンロード → トリム → サムネ生成 → YouTube → Notionアーカイブ
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import notion
import thumbnail
import trim
import youtube
import zoom

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 5件の録画マッピング定義
# Zoom録画のtopic → Notionマスターテーブル用の情報
# ---------------------------------------------------------------------------

RECORDING_MAP = [
    {
        "zoom_topic_match": "みくぽん講師",
        "title": "【グルコン】みくぽん講師 アフィリエイト・PR案件",
        "pattern": "対談",
        "lecturer_name": "みくぽん",
        "genre": "アフィリエイト",
        "thumbnail_text": "PR案件で月5万稼ぐ方法",
        "category": "グループコンサル",
        "student_name": "",
    },
    {
        "zoom_topic_match": "かりん講師",
        "title": "【1on1】かりん講師 x りのまさん SNS添削",
        "pattern": "対談",
        "lecturer_name": "かりん",
        "genre": "SNS運用",
        "thumbnail_text": "SNSフォロワー1万人への道",
        "category": "1on1",
        "student_name": "りのま",
    },
    {
        "zoom_topic_match": "ちゃみ",
        "title": "【グルコン】ちゃみ講師 コンテンツ作成術",
        "pattern": "対談",
        "lecturer_name": "ちゃみ",
        "genre": "コンテンツ作成",
        "thumbnail_text": "バズるコンテンツの作り方",
        "category": "グループコンサル",
        "student_name": "",
    },
    {
        "zoom_topic_match": "きたじまあやな",
        "title": "【1on1】はなこ講師 x きたじまあやなさん ライティング",
        "pattern": "対談",
        "lecturer_name": "はなこ",
        "genre": "ライティング",
        "thumbnail_text": "読まれるライティング添削",
        "category": "1on1",
        "student_name": "きたじまあやな",
    },
    {
        "zoom_topic_match": "Levelaマネタイズ",
        "title": "【対談】たっちー講師 マネタイズ成功の秘訣",
        "pattern": "対談",
        "lecturer_name": "たっちー",
        "genre": "マネタイズ",
        "thumbnail_text": "月収100万への最短ルート",
        "category": "講師対談",
        "student_name": "",
    },
]


def get_zoom_recordings() -> list[dict]:
    """Zoom APIから過去30日間の録画一覧を取得"""
    today = datetime.now()
    from_date = "2026-01-15"
    to_date = today.strftime("%Y-%m-%d")

    logger.info("Zoom録画一覧を取得中: %s ~ %s", from_date, to_date)
    recordings = zoom.list_recordings(from_date, to_date)
    logger.info("取得した録画ミーティング数: %d", len(recordings))
    return recordings


def match_zoom_to_config(recordings: list[dict]) -> list[dict]:
    """Zoom録画をRECORDING_MAPとマッチング"""
    matched = []

    for config in RECORDING_MAP:
        keyword = config["zoom_topic_match"]
        found = False
        for rec in recordings:
            topic = rec.get("topic", "")
            if keyword in topic:
                # MP4ファイルを見つける
                mp4_files = [
                    f for f in rec.get("recording_files", [])
                    if f.get("file_type") == "MP4"
                ]
                if not mp4_files:
                    logger.warning("  MP4ファイルなし: %s", topic)
                    continue

                # 最大サイズのMP4を選択（メインの録画）
                best_file = max(mp4_files, key=lambda f: f.get("file_size", 0))

                matched.append({
                    "config": config,
                    "zoom_meeting": rec,
                    "recording_file": best_file,
                })
                logger.info(
                    "  マッチ: %s → %s (%.1f MB)",
                    keyword,
                    topic,
                    best_file.get("file_size", 0) / (1024 * 1024),
                )
                found = True
                break

        if not found:
            # Zoom録画が見つからない場合、最初の未マッチ録画を使用
            logger.warning("  '%s' のZoom録画が見つかりません", keyword)

    return matched


def create_master_records(matched: list[dict]) -> list[dict]:
    """Notionマスターテーブルに5件のレコードを作成"""
    logger.info("\n=== Notionマスターテーブルにレコード作成 ===")

    headers = notion._headers()
    created = []

    for item in matched:
        config = item["config"]
        zoom_meeting = item["zoom_meeting"]
        start_time = zoom_meeting.get("start_time", "")

        properties = {
            "タイトル": {"title": [{"text": {"content": config["title"]}}]},
            "パターン": {"select": {"name": config["pattern"]}},
            "講師名": {"rich_text": [{"text": {"content": config["lecturer_name"]}}]},
            "ジャンル": {"select": {"name": config["genre"]}},
            "サムネ文言": {"rich_text": [{"text": {"content": config["thumbnail_text"]}}]},
            "種別": {"select": {"name": config["category"]}},
            "ステータス": {"select": {"name": "入力済み"}},
        }

        if config["student_name"]:
            properties["生徒名"] = {
                "rich_text": [{"text": {"content": config["student_name"]}}]
            }

        if start_time:
            properties["開始時間"] = {"date": {"start": start_time}}

        payload = {
            "parent": {"database_id": notion.NOTION_MASTER_DB_ID},
            "properties": properties,
        }

        resp = requests.post(
            f"{notion.BASE_URL}/pages",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        page_id = page["id"]

        logger.info(
            "  作成: %s (page_id=%s, start=%s)",
            config["title"],
            page_id,
            start_time,
        )

        item["page_id"] = page_id
        created.append(item)
        time.sleep(0.5)

    logger.info("マスターテーブルに %d 件作成完了", len(created))
    return created


def process_single(item: dict, tmp_dir: str, idx: int, total: int) -> dict:
    """1件分のフルパイプラインを実行"""
    config = item["config"]
    page_id = item["page_id"]
    recording_file = item["recording_file"]
    title = config["title"]

    result = {
        "title": title,
        "lecturer": config["lecturer_name"],
        "category": config["category"],
        "status": "PENDING",
    }

    logger.info(
        "\n{'='*60}\n[%d/%d] %s\n{'='*60}",
        idx, total, title,
    )

    try:
        # 1. ステータスを「処理中」に更新
        notion.update_status(page_id, "処理中")
        logger.info("  Step 1: ステータス → 処理中")

        # 2. Zoom録画ダウンロード
        logger.info("  Step 2: Zoom録画ダウンロード中...")
        download_url = recording_file["download_url"]
        access_token = zoom.get_access_token()
        raw_path = os.path.join(tmp_dir, f"{idx}_raw.mp4")
        zoom.download_recording(download_url, access_token, raw_path)
        file_size_mb = os.path.getsize(raw_path) / (1024 * 1024)
        logger.info("  ダウンロード完了: %.1f MB", file_size_mb)

        # 3. 無音トリム
        logger.info("  Step 3: 無音トリム中...")
        trimmed_path = os.path.join(tmp_dir, f"{idx}_trimmed.mp4")
        trimmed_path = trim.auto_trim(raw_path, trimmed_path)
        logger.info("  トリム完了: %s", os.path.basename(trimmed_path))

        # 4. サムネイル生成（バリデーション付き）
        logger.info("  Step 4: サムネイル生成中...")
        record = {
            "pattern": config["pattern"],
            "lecturer_name": config["lecturer_name"],
            "thumbnail_text": config["thumbnail_text"],
            "genre": config["genre"],
            "category": config["category"],
            "title": title,
            "student_name": config["student_name"],
            "page_id": page_id,
        }
        thumb_path = thumbnail.generate_thumbnail_validated(
            record, base_dir=PROJECT_ROOT, max_attempts=3
        )
        logger.info("  サムネイル生成完了: %s", os.path.basename(thumb_path))

        # 5. YouTube アップロード
        logger.info("  Step 5: YouTube アップロード中...")
        video_id = youtube.upload_video(
            file_path=trimmed_path,
            title=title,
            description=f"講師: {config['lecturer_name']} | 種別: {config['category']} | ジャンル: {config['genre']}",
        )
        youtube_url = youtube.get_video_url(video_id)
        logger.info("  YouTube URL: %s", youtube_url)

        # サムネイルをYouTubeに設定
        youtube.set_thumbnail(video_id, thumb_path)
        logger.info("  YouTubeサムネイル設定完了")

        # 6. サムネイル画像をGitHubにアップロード（Notionカバー用）
        # GitHubアップロードは手動のため、YouTube auto-generated URLを使用
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

        # 7. Notion動画アーカイブに登録
        logger.info("  Step 6: Notion動画アーカイブ登録中...")
        archive_page_id = notion.create_video_record(
            title=title,
            category=config["category"],
            date=item["zoom_meeting"].get("start_time", "")[:10],
            lecturer=config["lecturer_name"],
            youtube_url=youtube_url,
            thumbnail_url=thumbnail_url,
        )
        logger.info("  アーカイブ登録完了: %s", archive_page_id)

        # 8. マスターレコードを「完了」に更新
        notion.update_status(page_id, "完了", youtube_url=youtube_url)
        logger.info("  ステータス → 完了")

        result["status"] = "OK"
        result["youtube_url"] = youtube_url
        result["thumbnail"] = os.path.basename(thumb_path)

    except Exception as e:
        logger.exception("  エラー発生: %s", e)
        result["status"] = f"ERROR: {e}"

        try:
            notion.update_status(page_id, "エラー", error_msg=str(e))
        except Exception:
            pass

    return result


def main():
    print("\n" + "=" * 60)
    print("  SNS Club Portal - フルパイプライン実行")
    print("  Zoom → Notion → サムネ → YouTube → アーカイブ")
    print("=" * 60 + "\n")

    # Step 1: Zoom録画一覧を取得
    recordings = get_zoom_recordings()
    if not recordings:
        print("Zoom録画が見つかりませんでした。")
        return

    for rec in recordings:
        topic = rec.get("topic", "")
        files = rec.get("recording_files", [])
        mp4_count = sum(1 for f in files if f.get("file_type") == "MP4")
        logger.info("  %s (MP4: %d files)", topic, mp4_count)

    # Step 2: 5件マッチング
    matched = match_zoom_to_config(recordings)
    if not matched:
        print("マッチする録画が見つかりませんでした。")
        return

    print(f"\n--- {len(matched)}件のZoom録画をマッチ ---")
    for i, m in enumerate(matched, 1):
        c = m["config"]
        print(f"  {i}. {c['title']} [{c['category']}] 講師: {c['lecturer_name']}")

    # Step 3: Notionマスターテーブルに登録
    created = create_master_records(matched)

    # Step 4: 各レコードでパイプライン実行
    tmp_dir = tempfile.mkdtemp(prefix="cs_pipeline_")
    logger.info("一時ディレクトリ: %s", tmp_dir)

    results = []
    for i, item in enumerate(created, 1):
        result = process_single(item, tmp_dir, i, len(created))
        results.append(result)
        if i < len(created):
            time.sleep(3)  # API rate limit

    # サマリー
    print("\n\n" + "=" * 60)
    print("  結果サマリー")
    print("=" * 60)
    for r in results:
        status = "✅" if r["status"] == "OK" else "❌"
        yt = r.get("youtube_url", "-")
        print(f"  {status} {r['lecturer']:8s} | {r['category']:12s} | {r['status']}")
        if yt != "-":
            print(f"     YouTube: {yt}")
    print("=" * 60)

    # クリーンアップ
    logger.info("一時ファイル削除: %s", tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
