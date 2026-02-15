"""マネタイズ動画講義チャンネルを再スクレイピング
全スレッドカードをスクロールして漏れなく取得する
"""

import json
import re
import subprocess
import time


CHANNEL_URL = "https://discord.com/channels/1398982066682593420/1411044183032201439"


def run_js(js_code: str) -> str:
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "Google Chrome" to execute front window\'s'
        f' active tab javascript "{escaped}"'
    )
    r = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=15
    )
    return r.stdout.strip()


def open_url(url: str):
    script = f'tell application "Google Chrome" to set URL of active tab of front window to "{url}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def get_all_card_titles() -> list[str]:
    """フォーラムの全カードタイトルを取得"""
    raw = run_js(
        r"""(function() {
        var cards = document.querySelectorAll('[class*="card_"][class*="mainCard"]');
        var titles = [];
        cards.forEach(function(c) {
            var t = c.querySelector('[class*="title"]');
            if (t) titles.push(t.textContent.trim());
        });
        return JSON.stringify(titles);
    })()"""
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def scroll_down():
    """フォーラムをスクロールダウン"""
    run_js(
        r"""(function() {
        var container = document.querySelector('[class*="container_"][class*="themed_"]');
        if (!container) {
            // Try alternative selectors
            container = document.querySelector('[class*="scrollerBase_"]');
        }
        if (!container) {
            container = document.querySelector('[class*="content_"]');
        }
        if (container) {
            container.scrollTop += 500;
            return 'SCROLLED';
        }
        // Fallback: scroll the main content area
        window.scrollBy(0, 500);
        return 'SCROLLED_WINDOW';
    })()"""
    )


def click_past_posts():
    """「過去の投稿」ボタンをクリック"""
    result = run_js(
        r"""(function() {
        var divs = document.querySelectorAll('div');
        for (var i = 0; i < divs.length; i++) {
            if (divs[i].textContent.trim() === '過去の投稿' && divs[i].offsetParent !== null) {
                divs[i].click();
                return 'CLICKED';
            }
        }
        return 'NOT_FOUND';
    })()"""
    )
    return result


def click_card_by_index(idx: int) -> str:
    return run_js(
        f"""(function() {{
        var cards = document.querySelectorAll('[class*="card_"][class*="mainCard"]');
        if ({idx} < cards.length) {{
            cards[{idx}].click();
            return 'CLICKED';
        }}
        return 'OUT_OF_RANGE';
    }})()"""
    )


def get_youtube_links() -> list[str]:
    raw = run_js(
        r"""(function() {
        var links = [];
        document.querySelectorAll('a[href]').forEach(function(a) {
            var href = a.getAttribute('href');
            if (href && (
                href.indexOf('youtube.com/watch') >= 0 ||
                href.indexOf('youtu.be/') >= 0
            )) {
                if (links.indexOf(href) === -1) links.push(href);
            }
        });
        var allText = document.body.innerText;
        var matches = allText.match(/https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[^\s<>)]+/g);
        if (matches) {
            matches.forEach(function(m) {
                if (links.indexOf(m) === -1) links.push(m);
            });
        }
        return JSON.stringify(links);
    })()"""
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def go_back():
    run_js("history.back()")


def main():
    print("=" * 60)
    print("マネタイズ動画講義チャンネル 再スクレイピング")
    print("=" * 60)

    # Step 1: チャンネルを開く
    print("\n1. チャンネルを開いています...")
    open_url(CHANNEL_URL)
    time.sleep(7)

    # Step 2: 「過去の投稿」をクリック
    print("2. 「過去の投稿」を展開...")
    r = click_past_posts()
    print(f"   → {r}")
    time.sleep(3)

    # Step 3: スクロールして全カードを読み込み
    print("3. スクロールして全カード読み込み...")
    prev_count = 0
    for scroll_attempt in range(20):
        scroll_down()
        time.sleep(1.5)
        titles = get_all_card_titles()
        if len(titles) == prev_count and scroll_attempt > 3:
            break
        prev_count = len(titles)
        print(f"   スクロール {scroll_attempt+1}: {len(titles)} カード検出")

    # Step 4: 全カードタイトル表示
    titles = get_all_card_titles()
    print(f"\n全カード: {len(titles)}件")
    for i, t in enumerate(titles):
        print(f"  {i+1:2d}. {t}")

    # Step 5: 各カードをクリックしてYouTubeリンク取得
    print(f"\n4. 各カードのYouTubeリンク取得...")
    all_records = []

    for idx, title in enumerate(titles):
        print(f"\n  [{idx+1}/{len(titles)}] {title}")

        click_card_by_index(idx)
        time.sleep(4)

        links = get_youtube_links()
        print(f"    → YouTube: {links[:2]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
        })

        go_back()
        time.sleep(3)

    # 保存
    output_path = "assets/discord_monetize_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)}件")
    print(f"保存先: {output_path}")
    print(f"{'=' * 60}")

    # 既存データとの差分確認
    existing_titles = {
        "4-8_個別相談・セールス", "4-6_価格設計", "3-6_収益分析と改善サイクル",
        "3-5_アフィリエイト：ストーリーズ編", "3-4_アフィリエイト：投稿編",
        "3-2_ASP登録から案件選定までの手順", "3-1_アフィリエイト基礎と仕組み理解",
        "2-2_企業にアプローチする方法", "2-1_企業案件の全体像",
        "1-4 _コンプライアンス", "1-3_収益化までのステップ",
        "1-2 _マネタイズマインドセット",
    }

    print("\n新規発見:")
    for r in all_records:
        if r["title"] not in existing_titles:
            print(f"  🆕 {r['title']} → {r['youtube_links'][:1]}")


if __name__ == "__main__":
    main()
