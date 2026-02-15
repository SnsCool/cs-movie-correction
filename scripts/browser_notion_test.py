"""
browser-use を使って Notion マスターテーブルからデータを取得し、
サムネイル生成 → AI検証 → Discord送信 のフルパイプラインを実行する。
"""

import asyncio
import json
import os
import sys
import logging
import time
import re

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from browser_use import Agent, Browser, ChatGoogle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTION_MASTER_DB_URL = "https://www.notion.so/300f3b0fba8581a7b097e41110ce3148"


def extract_records_from_result(result) -> list[dict]:
    """AgentHistoryList から JSON レコードを抽出する。"""
    # result の文字列表現全体からJSONを探す
    result_text = str(result)

    # extracted_content 内のJSONを探す
    records = []
    # 複数のJSON objectを個別にパース
    for match in re.finditer(r'\{[^{}]*"タイトル"[^{}]*\}', result_text):
        try:
            obj = json.loads(match.group())
            # 重複チェック
            if not any(r.get("タイトル") == obj.get("タイトル") for r in records):
                records.append(obj)
        except json.JSONDecodeError:
            pass

    # JSON配列も探す
    if not records:
        match = re.search(r'\[[\s\S]*?\{[\s\S]*?"タイトル"[\s\S]*?\}[\s\S]*?\]', result_text)
        if match:
            try:
                records = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return records


async def main():
    # Gemini をブラウザ制御用LLMとして使用
    llm = ChatGoogle(
        model="gemini-2.0-flash",
        api_key=os.environ["GEMINI_API_KEY"],
    )

    # ヘッドフルモード（ブラウザを表示）
    browser = Browser(
        headless=False,
        disable_security=True,
    )

    # Step 1: Notion にアクセスしてデータを取得
    task = f"""
    以下の手順を実行してください:

    1. {NOTION_MASTER_DB_URL} にアクセスしてください
    2. もしログインページが表示された場合、30秒間待ってください（ユーザーが手動でログインします）
    3. テーブルが表示されたら、右にスクロールして全ての列を確認してください
    4. テーブルの各行から以下の列の情報を正確に読み取ってください（全行）:
       - タイトル（Name列、最初の列）
       - パターン（「対談」「グルコン」「1on1」のいずれか）
       - 講師名
       - ジャンル
       - サムネ文言
       - 種別（「グループコンサル」「マネタイズ講座」「1on1添削」のいずれか）
       - 生徒名（1on1の場合のみ）
       - ステータス
    5. nullやemptyの場合もそのまま含めてください
    6. 最終的に全行のデータをJSON配列として返してください

    重要:
    - テーブルを右にスクロールして見えない列のデータも読み取ってください
    - 各行をクリックして詳細を確認するとより正確なデータが取れます
    - 最終出力は必ず JSON 配列にしてください
    """

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_actions_per_step=5,
    )

    print("\n=== ブラウザが開きます。Notionのログインが必要な場合は手動で完了してください ===\n")

    result = await agent.run(max_steps=40)

    print("\n=== ブラウザエージェント結果 ===")

    # 結果からJSONを抽出
    records = extract_records_from_result(result)

    if records:
        print(f"取得レコード数: {len(records)}")
        for r in records:
            print(f"  - {r}")
    else:
        # フォールバック: str全体から探す
        result_text = str(result)
        match = re.search(r'\[{.*}\]', result_text, re.DOTALL)
        if match:
            try:
                records = json.loads(match.group())
                print(f"取得レコード数（フォールバック）: {len(records)}")
            except json.JSONDecodeError:
                pass

    if not records:
        print("レコードが取得できませんでした。")
        print("Notion APIフォールバックでデータを取得します...")

        # Notion API で直接取得
        import requests as req
        notion_token = os.environ.get("NOTION_TOKEN", "")
        db_id = os.environ.get("NOTION_MASTER_DB_ID", "")
        if notion_token and db_id:
            headers = {
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
            resp = req.post(
                f"https://api.notion.com/v1/databases/{db_id}/query",
                headers=headers,
                json={},
                timeout=30,
            )
            if resp.ok:
                pages = resp.json().get("results", [])
                for page in pages:
                    props = page.get("properties", {})
                    rec = {}
                    for key, val in props.items():
                        if val["type"] == "title":
                            parts = val.get("title", [])
                            rec["タイトル"] = parts[0]["plain_text"] if parts else ""
                        elif val["type"] == "select":
                            sel = val.get("select")
                            rec[key] = sel["name"] if sel else None
                        elif val["type"] == "rich_text":
                            parts = val.get("rich_text", [])
                            rec[key] = parts[0]["plain_text"] if parts else ""
                        elif val["type"] == "status":
                            st = val.get("status")
                            rec[key] = st["name"] if st else None
                    records.append(rec)
                print(f"Notion API で {len(records)} 件取得")

    if not records:
        print("データ取得に失敗しました。")
        return

    # Step 2: 各レコードでサムネイル生成 → 検証 → Discord送信
    import thumbnail
    import requests

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    results_summary = []

    for i, rec in enumerate(records[:6], 1):
        lecturer = rec.get("講師名", rec.get("lecturer_name", "")) or ""
        title = rec.get("タイトル", rec.get("title", "")) or ""
        print(f"\n======== [{i}/{min(len(records), 6)}] {lecturer or title} ========")

        # Notion データを thumbnail.py が期待する形式に変換
        record = {
            "pattern": rec.get("パターン", rec.get("pattern", "")) or "対談",
            "lecturer_name": lecturer,
            "thumbnail_text": rec.get("サムネ文言", rec.get("thumbnail_text", "")) or "",
            "genre": rec.get("ジャンル", rec.get("genre", "")) or "",
            "category": rec.get("種別", rec.get("category", "")) or "グループコンサル",
            "title": title,
            "student_name": rec.get("生徒名", rec.get("student_name", "")) or "",
            "page_id": "test-page-id",
        }

        # 講師名が空の場合、タイトルから推測
        if not record["lecturer_name"] and record["title"]:
            # 「【グルコン】じゅん講師 PR案件」→「じゅん講師」
            m = re.search(r'【.*?】\s*(\S+講師|\S+)', record["title"])
            if m:
                record["lecturer_name"] = m.group(1)

        if not record["lecturer_name"]:
            print("  スキップ（講師名なし）")
            results_summary.append({"name": "不明", "discord": "SKIP"})
            continue

        try:
            thumb_path = thumbnail.generate_thumbnail_validated(
                record, base_dir=PROJECT_ROOT, max_attempts=3
            )
            print(f"  サムネ: {os.path.basename(thumb_path)}")
        except Exception as e:
            print(f"  エラー: {e}")
            results_summary.append({
                "name": record["lecturer_name"],
                "discord": "SKIP",
                "error": str(e),
            })
            time.sleep(3)
            continue

        # Discord送信
        discord_status = "NO WEBHOOK"
        if webhook_url:
            embed = {
                "title": "\U0001f3ac 新しい動画がアップロードされました",
                "description": record["title"],
                "url": "https://youtu.be/test",
                "color": 0x58ACFF,
                "image": {"url": "attachment://thumbnail.png"},
                "fields": [
                    {"name": "講師", "value": record["lecturer_name"], "inline": True},
                    {"name": "種別", "value": record["category"], "inline": True},
                    {"name": "ジャンル", "value": record["genre"], "inline": True},
                    {"name": "サムネ文言", "value": record["thumbnail_text"] or "未設定", "inline": False},
                ],
            }
            payload_wrapper = json.dumps({"embeds": [embed]})
            try:
                with open(thumb_path, "rb") as f:
                    files_data = {
                        "payload_json": (None, payload_wrapper, "application/json"),
                        "files[0]": ("thumbnail.png", f, "image/png"),
                    }
                    resp = requests.post(webhook_url, files=files_data, timeout=30)
                discord_status = "OK" if resp.ok else f"NG ({resp.status_code})"
            except Exception as e:
                discord_status = f"ERR: {e}"

        print(f"  Discord: {discord_status}")
        results_summary.append({
            "name": record["lecturer_name"],
            "path": thumb_path,
            "discord": discord_status,
        })
        time.sleep(2)

    # サマリー
    print("\n\n========== 結果サマリー ==========")
    for r in results_summary:
        fname = os.path.basename(r.get("path", "NONE")) if r.get("path") else "NONE"
        print(f"  {r.get('name', '不明'):10s} | Discord: {r.get('discord', '?'):5s} | {fname}")
    print("==================================")


if __name__ == "__main__":
    asyncio.run(main())
