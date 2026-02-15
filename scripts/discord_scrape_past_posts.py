"""「過去の投稿」セクション（スクロール後）の全スレッドからYouTubeリンク取得"""

import json
import subprocess
import time

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1411044183032201439"
CHANNEL_URL = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}"

# 取得対象の不足タイトル
MISSING_TITLES = [
    "1-1 _基礎_Instagram収益化の全体像",
    "2-3_案件単価交渉・条件交渉",
    "3-3_アフィリエイト型投稿の作り方",
    "4-1 コンテンツ販売の全体像",
    "4-2_自社商品ーコンセプト設計",
    "4-3_特典設計",
    "4-4_商品作成",
    "4-5_販売導線構築",
    "4-7_ストーリーローンチ",
    "5-1 運用代行の全体像",
    "5-2 料金設計",
]


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


def get_current_url() -> str:
    return run_js("window.location.href")


def scroll_to_bottom():
    """フォーラムを最下部までスクロール"""
    for i in range(15):
        run_js(
            r"""(function() {
            var containers = document.querySelectorAll('[class*="scrollerBase_"], [class*="scroller_"]');
            containers.forEach(function(c) {
                if (c.scrollHeight > c.clientHeight) {
                    c.scrollTop += 600;
                }
            });
        })()"""
        )
        time.sleep(1)


def get_card_titles() -> list[str]:
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


def click_card_by_title(target_title: str) -> str:
    escaped_title = target_title.replace("'", "\\'").replace("\\", "\\\\")
    return run_js(
        f"""(function() {{
        var cards = document.querySelectorAll('[class*="card_"][class*="mainCard"]');
        for (var i = 0; i < cards.length; i++) {{
            var t = cards[i].querySelector('[class*="title"]');
            if (t && t.textContent.trim() === '{escaped_title}') {{
                // カードが見えるようにスクロール
                cards[i].scrollIntoView({{behavior: 'instant', block: 'center'}});
                return 'FOUND_' + i;
            }}
        }}
        return 'NOT_FOUND';
    }})()"""
    )


def click_card_and_wait(target_title: str) -> str:
    escaped_title = target_title.replace("'", "\\'").replace("\\", "\\\\")
    # まずスクロールしてカードを表示
    run_js(
        f"""(function() {{
        var cards = document.querySelectorAll('[class*="card_"][class*="mainCard"]');
        for (var i = 0; i < cards.length; i++) {{
            var t = cards[i].querySelector('[class*="title"]');
            if (t && t.textContent.trim() === '{escaped_title}') {{
                cards[i].scrollIntoView({{behavior: 'instant', block: 'center'}});
                break;
            }}
        }}
    }})()"""
    )
    time.sleep(1)
    # クリック
    return run_js(
        f"""(function() {{
        var cards = document.querySelectorAll('[class*="card_"][class*="mainCard"]');
        for (var i = 0; i < cards.length; i++) {{
            var t = cards[i].querySelector('[class*="title"]');
            if (t && t.textContent.trim() === '{escaped_title}') {{
                cards[i].click();
                return 'CLICKED';
            }}
        }}
        return 'NOT_FOUND';
    }})()"""
    )


def get_youtube_from_thread() -> list[str]:
    raw = run_js(
        r"""(function() {
        var links = [];
        var msgs = document.querySelectorAll('[class*="messageContent_"], [id*="message-content"]');
        msgs.forEach(function(msg) {
            msg.querySelectorAll('a[href]').forEach(function(a) {
                var href = a.getAttribute('href');
                if (href && (
                    href.indexOf('youtube.com/watch') >= 0 ||
                    href.indexOf('youtu.be/') >= 0
                )) {
                    if (links.indexOf(href) === -1) links.push(href);
                }
            });
            var text = msg.textContent;
            var matches = text.match(/https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[^\s<>)]+/g);
            if (matches) {
                matches.forEach(function(m) {
                    if (links.indexOf(m) === -1) links.push(m);
                });
            }
        });
        document.querySelectorAll('[class*="embed_"]').forEach(function(embed) {
            embed.querySelectorAll('a[href]').forEach(function(a) {
                var href = a.getAttribute('href');
                if (href && (
                    href.indexOf('youtube.com/watch') >= 0 ||
                    href.indexOf('youtu.be/') >= 0
                )) {
                    if (links.indexOf(href) === -1) links.push(href);
                }
            });
        });
        return JSON.stringify(links);
    })()"""
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def main():
    print("=" * 60)
    print("「過去の投稿」セクションの全スレッド取得")
    print("=" * 60)

    all_records = []

    for title in MISSING_TITLES:
        print(f"\n--- {title} ---")

        # 1. チャンネルを開く（毎回リフレッシュ）
        open_url(CHANNEL_URL)
        time.sleep(7)

        # 2. 「過去の投稿」が見えるまでスクロール
        scroll_to_bottom()
        time.sleep(2)

        # 3. カード一覧確認
        cards = get_card_titles()
        if title not in cards:
            print(f"  カード未検出 (表示中: {len(cards)}件)")
            # もう少しスクロール
            scroll_to_bottom()
            time.sleep(2)
            cards = get_card_titles()
            if title not in cards:
                print(f"  再試行後も未検出。スキップ。")
                print(f"  表示中カード: {cards}")
                continue

        # 4. カードをクリック
        result = click_card_and_wait(title)
        print(f"  クリック: {result}")
        time.sleep(5)

        # 5. Thread ID取得
        url = get_current_url()
        parts = url.rstrip("/").split("/")
        thread_id = None
        if "threads" in parts:
            ti = parts.index("threads")
            if ti + 1 < len(parts):
                thread_id = parts[ti + 1]
        elif parts[-1] != CHANNEL_ID:
            thread_id = parts[-1]

        print(f"  Thread ID: {thread_id}")
        print(f"  URL: {url}")

        # 6. 直接スレッドURLに再アクセス（正確なリンク取得）
        if thread_id:
            direct_url = f"https://discord.com/channels/{GUILD_ID}/{thread_id}"
            open_url(direct_url)
            time.sleep(6)

        # 7. YouTubeリンク取得
        links = get_youtube_from_thread()
        print(f"  YouTube: {links[:3]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
            "thread_id": thread_id or "",
        })

    # 保存
    output = "assets/discord_past_posts.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)} 件")
    print(f"保存先: {output}")
    print(f"{'=' * 60}")

    for r in all_records:
        yt = r["youtube_links"][0] if r["youtube_links"] else "NO LINK"
        print(f"  {r['title']} → {yt} (thread: {r['thread_id']})")

    # YouTube重複チェック
    print("\n--- YouTube重複チェック ---")
    yt_to_title = {}
    for r in all_records:
        for link in r["youtube_links"]:
            if link in yt_to_title:
                print(f"  重複: {link}")
                print(f"    → {yt_to_title[link]}")
                print(f"    → {r['title']}")
            else:
                yt_to_title[link] = r["title"]


if __name__ == "__main__":
    main()
