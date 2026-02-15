"""E2Eテスト: Webフォーム送信 → Notion確認（3パターン）

Zoom録画情報を基に、3パターンそれぞれでフォームを送信し、
Notionマスターテーブルにレコードが正しく作成されることを確認する。
"""

import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import notion

FORM_URL = "https://sns-club-portal-production.up.railway.app"

# Zoom録画から取得した実データ
ZOOM_RECORDINGS = [
    {
        "topic": "Levelaマネタイズのパーソナルミーティングルーム",
        "start_time": "2026-02-09T00:01:22Z",
    },
    {
        "topic": "かりん講師✖️りのまさん",
        "start_time": "2026-02-04T01:59:53Z",
    },
    {
        "topic": "ちゃみミーティング",
        "start_time": "2026-01-29T14:00:30Z",
    },
]

# 3パターンのテストデータ
TEST_CASES = [
    {
        "name": "パターン1テスト（2人対談）",
        "pattern": "パターン1",
        "zoom_idx": 0,
        "form_data": {
            "title": "[E2Eテスト] グルコン｜陸講師×はなこ講師",
            "thumbnail_text": "今月の献立",
            "category": "グルコン",
            "lecturer_name": "陸講師×はなこ講師",
            "lecturer_image1": "01_陸_1人.png",
            "lecturer_image2": "15_はなこ_1人.png",
        },
    },
    {
        "name": "パターン2テスト（スマホ）",
        "pattern": "パターン2",
        "zoom_idx": 1,
        "form_data": {
            "title": "[E2Eテスト] 講座｜かりん講師",
            "thumbnail_text": "SNS運用の極意",
            "category": "講座",
            "lecturer_name_p2": "かりん講師",
            "lecturer_image_single": "18_かりん_1人.png",
        },
    },
    {
        "name": "パターン3テスト（1on1）",
        "pattern": "パターン3",
        "zoom_idx": 2,
        "form_data": {
            "title": "[E2Eテスト] 1on1｜ちゃみ講師×えむさん",
            "thumbnail_text": "アフィ案件 今後の計画",
            "category": "1on1",
            "lecturer_name_p3": "ちゃみ講師",
            "student_name": "えむさん",
        },
    },
]


def format_start_time(zoom_iso: str) -> str:
    """Zoom ISO8601 → datetime-local形式"""
    dt = datetime.fromisoformat(zoom_iso.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%dT%H:%M")


def submit_form(test_case: dict) -> dict:
    """Webフォームに送信して結果を返す"""
    zoom_rec = ZOOM_RECORDINGS[test_case["zoom_idx"]]
    start_time = format_start_time(zoom_rec["start_time"])

    # まずGETでCSRFトークンとセッションを取得
    session = requests.Session()
    get_resp = session.get(FORM_URL, timeout=30)
    if get_resp.status_code != 200:
        return {"ok": False, "error": f"GET / failed: {get_resp.status_code}"}

    # CSRFトークンを抽出
    html = get_resp.text
    import re
    csrf_match = re.search(r'name="_csrf_token"\s+value="([^"]+)"', html)
    if not csrf_match:
        return {"ok": False, "error": "CSRFトークンが見つかりません"}
    csrf_token = csrf_match.group(1)

    # フォームデータ構築
    data = {
        "_csrf_token": csrf_token,
        "pattern": test_case["pattern"],
        "start_time": start_time,
    }
    data.update(test_case["form_data"])

    # POST送信
    post_resp = session.post(f"{FORM_URL}/submit", data=data, timeout=30)

    return {
        "ok": post_resp.status_code == 200,
        "status_code": post_resp.status_code,
        "html": post_resp.text,
        "title": test_case["form_data"]["title"],
        "start_time": start_time,
    }


def verify_notion(title: str) -> dict | None:
    """Notionマスターテーブルから該当レコードを検索"""
    db_id = os.environ.get("NOTION_MASTER_DB_ID", "300f3b0f-ba85-81a7-b097-e41110ce3148")
    headers = notion._headers()
    url = f"https://api.notion.com/v1/databases/{db_id}/query"

    payload = {
        "filter": {
            "property": "タイトル",
            "title": {"contains": title.replace("[E2Eテスト] ", "")},
        },
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": 1,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    results = resp.json().get("results", [])
    if not results:
        return None

    return notion.parse_master_record(results[0])


def main():
    print("=" * 60)
    print("E2Eテスト: Webフォーム送信 → Notion確認")
    print(f"対象URL: {FORM_URL}")
    print("=" * 60)

    results = []

    for i, tc in enumerate(TEST_CASES, 1):
        zoom_rec = ZOOM_RECORDINGS[tc["zoom_idx"]]
        print(f"\n{'─' * 50}")
        print(f"[{i}/3] {tc['name']}")
        print(f"  Zoom録画: {zoom_rec['topic']}")
        print(f"  開始時間: {zoom_rec['start_time']}")
        print(f"  パターン: {tc['pattern']}")
        print(f"  タイトル: {tc['form_data']['title']}")
        print()

        # Step 1: フォーム送信
        print("  📤 フォーム送信中...")
        result = submit_form(tc)

        if not result["ok"]:
            print(f"  ❌ 送信失敗: status={result.get('status_code')} {result.get('error', '')}")
            # HTMLの一部を表示
            if "html" in result:
                # error-box の中身を探す
                import re
                errors = re.findall(r'<p>(.*?)</p>', result["html"][:2000])
                for e in errors[:5]:
                    print(f"     {e}")
            results.append({"test": tc["name"], "submit": False, "notion": False})
            continue

        print(f"  ✅ 送信成功 (HTTP {result['status_code']})")

        # Notionページへのリンクを抽出
        import re
        notion_url_match = re.search(r'href="(https://notion\.so/[^"]+)"', result["html"])
        if notion_url_match:
            print(f"  📎 Notion URL: {notion_url_match.group(1)}")

        # Step 2: Notion確認（少し待つ）
        print("  🔍 Notion確認中...")
        time.sleep(2)

        search_title = tc["form_data"]["title"].replace("[E2Eテスト] ", "")
        record = verify_notion(search_title)

        if record is None:
            print("  ❌ Notionレコードが見つかりません")
            results.append({"test": tc["name"], "submit": True, "notion": False})
            continue

        print(f"  ✅ Notionレコード確認")
        print(f"     page_id:      {record['page_id']}")
        print(f"     タイトル:     {record['title']}")
        print(f"     種別:         {record['category']}")
        print(f"     パターン:     {record['pattern']}")
        print(f"     ステータス:   {record['status']}")
        print(f"     サムネ文言:   {record['thumbnail_text']}")
        print(f"     講師名:      {record['lecturer_name']}")
        print(f"     開始時間:     {record['start_time']}")
        if record.get("lecturer_image1"):
            print(f"     講師画像①:   {record['lecturer_image1']}")
        if record.get("lecturer_image2"):
            print(f"     講師画像②:   {record['lecturer_image2']}")
        if record.get("student_name"):
            print(f"     生徒名:      {record['student_name']}")

        results.append({"test": tc["name"], "submit": True, "notion": True, "record": record})

    # サマリー
    print(f"\n{'=' * 60}")
    print("テスト結果サマリー")
    print(f"{'=' * 60}")
    all_pass = True
    for r in results:
        submit_icon = "✅" if r["submit"] else "❌"
        notion_icon = "✅" if r["notion"] else "❌"
        overall = "PASS" if r["submit"] and r["notion"] else "FAIL"
        if overall == "FAIL":
            all_pass = False
        print(f"  {r['test']}: 送信{submit_icon} Notion{notion_icon} → {overall}")

    print()
    if all_pass:
        print("🎉 全テスト PASS!")
    else:
        print("⚠️  一部テスト FAIL")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
