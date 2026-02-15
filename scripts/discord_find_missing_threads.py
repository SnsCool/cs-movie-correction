"""Discord マネタイズ動画講義チャンネルの全スレッドを検索

「過去の投稿」以外のセクション（アクティブ/ピン留め等）も含めて
全スレッドを取得し、見落としを発見する。
"""

import json
import subprocess
import time


CHANNEL_URL = "https://discord.com/channels/1398982066682593420/1411044183032201439"

# 既知の不足番号とそのスレッドID（判明分）
KNOWN_MISSING = {
    "1-1": {"thread_id": "1414684672180359249"},
    "3-3": {},
    "4-1": {},
    "4-2": {},
    "4-3": {},
    "4-4": {},
    "4-5": {},
    "4-7": {},
}


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


def get_all_thread_titles() -> list[str]:
    """ページ上の全スレッドタイトルを取得（全セクション）"""
    raw = run_js(
        r"""(function() {
        var results = [];
        // Method 1: カードタイトル
        document.querySelectorAll('[class*="card_"][class*="mainCard"]').forEach(function(c) {
            var t = c.querySelector('[class*="title"]');
            if (t) results.push(t.textContent.trim());
        });
        // Method 2: スレッド名リンク
        document.querySelectorAll('[class*="name_"][class*="overflow"]').forEach(function(n) {
            var text = n.textContent.trim();
            if (text && results.indexOf(text) === -1) results.push(text);
        });
        // Method 3: role=listitem内のテキスト
        document.querySelectorAll('[role="listitem"]').forEach(function(li) {
            var h = li.querySelector('h3, [class*="heading"]');
            if (h) {
                var text = h.textContent.trim();
                if (text && results.indexOf(text) === -1) results.push(text);
            }
        });
        return JSON.stringify(results);
    })()"""
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def get_all_links_and_text() -> str:
    """ページ上の全テキストから動画番号パターンを検索"""
    raw = run_js(
        r"""(function() {
        var text = document.body.innerText;
        var matches = text.match(/\d+-\d+[_\s].+/g);
        return JSON.stringify(matches || []);
    })()"""
    )
    return raw


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


def scroll_up():
    run_js(
        r"""(function() {
        var container = document.querySelector('[class*="container_"][class*="themed_"]');
        if (!container) container = document.querySelector('[class*="scrollerBase_"]');
        if (!container) container = document.querySelector('[class*="content_"]');
        if (container) {
            container.scrollTop = 0;
            return 'SCROLLED_TOP';
        }
        window.scrollTo(0, 0);
        return 'SCROLLED_WINDOW_TOP';
    })()"""
    )


def scroll_down():
    run_js(
        r"""(function() {
        var container = document.querySelector('[class*="container_"][class*="themed_"]');
        if (!container) container = document.querySelector('[class*="scrollerBase_"]');
        if (!container) container = document.querySelector('[class*="content_"]');
        if (container) {
            container.scrollTop += 600;
            return 'SCROLLED';
        }
        window.scrollBy(0, 600);
        return 'SCROLLED_WINDOW';
    })()"""
    )


def go_back():
    run_js("history.back()")


def navigate_to_thread(thread_id: str):
    """特定のスレッドに直接ナビゲート"""
    url = f"https://discord.com/channels/1398982066682593420/1411044183032201439/threads/{thread_id}"
    open_url(url)


def get_thread_title() -> str:
    """現在開いているスレッドのタイトルを取得"""
    raw = run_js(
        r"""(function() {
        // Method 1: ヘッダーのタイトル
        var h = document.querySelector('[class*="title_"][class*="container_"] h3');
        if (h) return h.textContent.trim();
        // Method 2: チャンネルヘッダー
        var ch = document.querySelector('[class*="channelName_"]');
        if (ch) return ch.textContent.trim();
        // Method 3: heading要素
        var h2 = document.querySelector('h1, h2, h3');
        if (h2) return h2.textContent.trim();
        return '';
    })()"""
    )
    return raw


def main():
    print("=" * 60)
    print("Discord マネタイズ動画講義 - 全スレッド検索")
    print("=" * 60)

    all_found = []

    # ===========================================================
    # Phase 1: チャンネルページ全体をスキャン
    # ===========================================================
    print("\n--- Phase 1: チャンネル全体スキャン ---")
    open_url(CHANNEL_URL)
    time.sleep(7)

    # 上部セクション（アクティブスレッド等）をスキャン
    print("上部セクションをスキャン...")
    scroll_up()
    time.sleep(2)

    titles = get_all_thread_titles()
    print(f"  初期検出: {len(titles)} 件")
    for t in titles:
        print(f"    - {t}")

    text_matches = get_all_links_and_text()
    print(f"  テキストパターン: {text_matches[:500]}")

    # 全体をスクロールして取得
    print("\nスクロールして全体をスキャン...")
    all_titles = set(titles)
    for i in range(30):
        scroll_down()
        time.sleep(1.5)
        new_titles = get_all_thread_titles()
        for t in new_titles:
            if t not in all_titles:
                all_titles.add(t)
                print(f"  新規発見: {t}")

    print(f"\nPhase 1 合計: {len(all_titles)} 件")
    for t in sorted(all_titles):
        print(f"  - {t}")

    # ===========================================================
    # Phase 2: 既知スレッドIDで直接アクセス
    # ===========================================================
    print("\n--- Phase 2: 既知スレッドIDで直接アクセス ---")

    # 1-1 は確認済み
    thread_id = "1414684672180359249"
    print(f"\nスレッド {thread_id} (1-1) にアクセス...")
    navigate_to_thread(thread_id)
    time.sleep(5)

    title = get_thread_title()
    links = get_youtube_links()
    print(f"  タイトル: {title}")
    print(f"  YouTube: {links}")

    if title or links:
        all_found.append({
            "title": title or "1-1 _基礎_Instagram収益化の全体像",
            "youtube_links": links if links else ["https://youtu.be/Rw7tXxKaynA"],
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
            "thread_id": thread_id,
        })

    # ===========================================================
    # Phase 3: チャンネルに戻って各カードをクリックして詳細取得
    # ===========================================================
    print("\n--- Phase 3: 各スレッドの詳細取得 ---")
    open_url(CHANNEL_URL)
    time.sleep(7)

    # 「過去の投稿」クリック
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
    print(f"「過去の投稿」: {result}")
    time.sleep(3)

    # スクロールして全カードロード
    for i in range(15):
        scroll_down()
        time.sleep(1.5)

    # 全カードタイトル取得
    card_titles_raw = run_js(
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
        card_titles = json.loads(card_titles_raw)
    except json.JSONDecodeError:
        card_titles = []

    print(f"\nカード一覧: {len(card_titles)} 件")
    for t in card_titles:
        print(f"  - {t}")

    # アクティブスレッド一覧（カード以外）
    active_raw = run_js(
        r"""(function() {
        var results = [];
        // アクティブスレッド部分を検索
        var allElements = document.querySelectorAll('[class*="mainCard"], [class*="thread"], [class*="item"]');
        allElements.forEach(function(el) {
            var titleEl = el.querySelector('[class*="title"], [class*="name"], h3');
            if (titleEl) {
                var text = titleEl.textContent.trim();
                if (text && text.match(/\d+-\d+/) && results.indexOf(text) === -1) {
                    results.push(text);
                }
            }
        });
        return JSON.stringify(results);
    })()"""
    )
    print(f"\n動画番号パターン検出: {active_raw}")

    # ===========================================================
    # Phase 4: 上部の「ソート」を変更してすべて表示させる
    # ===========================================================
    print("\n--- Phase 4: ソート/フィルタ変更 ---")

    # ソートボタンクリック
    sort_result = run_js(
        r"""(function() {
        // ソートやフィルターのドロップダウンを探す
        var btns = document.querySelectorAll('button, [role="button"]');
        var results = [];
        btns.forEach(function(b) {
            var text = b.textContent.trim();
            if (text) results.push(text);
        });
        return JSON.stringify(results);
    })()"""
    )
    print(f"ボタン一覧: {sort_result[:500]}")

    # ===========================================================
    # 結果まとめ
    # ===========================================================
    print("\n" + "=" * 60)
    print("結果まとめ")
    print("=" * 60)

    existing = {
        "1-2", "1-3", "1-4",
        "2-1", "2-2",
        "3-1", "3-2", "3-4", "3-5", "3-6",
        "4-6", "4-8",
    }

    found_numbers = set()
    for t in all_titles | set(card_titles):
        import re
        m = re.match(r"(\d+-\d+)", t)
        if m:
            found_numbers.add(m.group(1))

    # 1-1 は確認済みで追加
    found_numbers.add("1-1")

    print(f"\n検出済み番号: {sorted(found_numbers)}")
    print(f"既存(Notion): {sorted(existing)}")

    still_missing = []
    for num in ["1-1", "3-3", "4-1", "4-2", "4-3", "4-4", "4-5", "4-7"]:
        if num not in found_numbers and num not in existing:
            still_missing.append(num)
        elif num == "1-1":
            print(f"  {num}: 発見済み（スレッドID確認済み）")

    if still_missing:
        print(f"\nまだ見つからない番号: {still_missing}")
    else:
        print("\n全番号が発見またはNotionに存在しています")

    # 見つかったスレッド情報を保存
    if all_found:
        output = "assets/discord_missing_threads.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(all_found, f, ensure_ascii=False, indent=2)
        print(f"\n保存: {output}")


if __name__ == "__main__":
    main()
