"""アクティブセクション表示切替 → 全スレッド取得

スレッドに直接アクセスしてから戻ることで、
フォーラムの表示をアクティブセクション表示に切り替える。
"""

import json
import subprocess
import time

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1411044183032201439"
CHANNEL_URL = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}"
KNOWN_THREAD = "1414684672180359249"  # 1-1のスレッドID

# Notionに既に存在するタイトル
EXISTING_TITLES = {
    "4-8_個別相談・セールス", "4-6_価格設計", "3-6_収益分析と改善サイクル",
    "3-5_アフィリエイト：ストーリーズ編", "3-4_アフィリエイト：投稿編",
    "3-2_ASP登録から案件選定までの手順", "3-1_アフィリエイト基礎と仕組み理解",
    "2-2_企業にアプローチする方法", "2-1_企業案件の全体像",
    "1-4 _コンプライアンス", "1-3_収益化までのステップ",
    "1-2 _マネタイズマインドセット",
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


def get_current_url() -> str:
    return run_js("window.location.href")


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
    escaped_title = target_title.replace("'", "\\'").replace('"', '\\"')
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
    print("Step 1: スレッドに直接アクセスしてビュー切替")
    print("=" * 60)

    # まず1-1スレッドに直接アクセス
    thread_url = f"https://discord.com/channels/{GUILD_ID}/{KNOWN_THREAD}"
    print(f"1-1スレッドにアクセス: {thread_url}")
    open_url(thread_url)
    time.sleep(6)

    # 1-1のYouTubeリンクを取得
    yt_1_1 = get_youtube_from_thread()
    print(f"1-1 YouTube: {yt_1_1}")

    # チャンネルに戻る
    print("\nチャンネルに戻る...")
    open_url(CHANNEL_URL)
    time.sleep(8)

    # カード一覧を確認
    cards = get_card_titles()
    print(f"\n表示カード: {len(cards)} 件")
    for t in cards:
        marker = "[既存]" if t in EXISTING_TITLES else "[NEW!]"
        print(f"  {marker} {t}")

    new_cards = [t for t in cards if t not in EXISTING_TITLES]
    print(f"\n新規カード: {len(new_cards)} 件")

    if len(new_cards) == 0:
        print("\n新規カードが見つかりません。DOM全体を検索...")
        # フォーラム内の全テキストを取得
        all_text = run_js(
            r"""(function() {
            var results = [];
            var all = document.querySelectorAll('*');
            for (var i = 0; i < all.length; i++) {
                var text = all[i].textContent.trim();
                if (text.match(/^[0-9]+-[0-9]+/) && text.length < 50) {
                    if (results.indexOf(text) === -1) results.push(text);
                }
            }
            return JSON.stringify(results);
        })()"""
        )
        print(f"番号パターン検出: {all_text[:500]}")

        # セクションヘッダーを確認
        sections = run_js(
            r"""(function() {
            var headers = [];
            document.querySelectorAll('h2, h3, [class*="header"], [class*="divider"]').forEach(function(h) {
                var text = h.textContent.trim();
                if (text && text.length < 50) headers.push(text);
            });
            return JSON.stringify(headers);
        })()"""
        )
        print(f"セクションヘッダー: {sections[:500]}")

        # ソートを変更してみる
        print("\nソートボタンを探す...")
        sort_info = run_js(
            r"""(function() {
            var btns = [];
            document.querySelectorAll('[class*="sort"], [class*="filter"], [class*="Sort"], [class*="Filter"]').forEach(function(b) {
                btns.push({tag: b.tagName, text: b.textContent.trim().substring(0, 30), class: b.className.substring(0, 50)});
            });
            return JSON.stringify(btns);
        })()"""
        )
        print(f"ソート/フィルタ要素: {sort_info[:500]}")

    # ===========================================================
    print("\n" + "=" * 60)
    print("Step 2: 各新規スレッドのThread IDとYouTubeリンク取得")
    print("=" * 60)

    all_records = []

    for title in new_cards:
        print(f"\n--- {title} ---")

        # チャンネルに戻る（スレッドから戻った後の状態を維持するため、1-1経由で）
        open_url(thread_url)
        time.sleep(4)
        open_url(CHANNEL_URL)
        time.sleep(6)

        # カードが表示されるか確認
        current_cards = get_card_titles()
        if title not in current_cards:
            print(f"  カード未検出、リトライ...")
            time.sleep(3)
            current_cards = get_card_titles()

        # カードクリック
        result = click_card_by_title(title)
        print(f"  クリック: {result}")

        if result != "CLICKED":
            print("  スキップ")
            continue

        time.sleep(4)

        # Thread ID取得
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

        # YouTubeリンク取得
        if thread_id:
            direct_url = f"https://discord.com/channels/{GUILD_ID}/{thread_id}"
            open_url(direct_url)
            time.sleep(6)

        links = get_youtube_from_thread()
        print(f"  YouTube: {links[:3]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
            "thread_id": thread_id or "",
        })

    # 1-1を追加
    all_records.append({
        "title": "1-1 _基礎_Instagram収益化の全体像",
        "youtube_links": yt_1_1 if yt_1_1 else ["https://youtu.be/Rw7tXxKaynA"],
        "tag": "マネタイズ",
        "channel": "マネタイズ動画講義",
        "thread_id": KNOWN_THREAD,
    })

    # 保存
    output = "assets/discord_active_threads_v4.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)} 件")
    print(f"保存先: {output}")
    print(f"{'=' * 60}")

    for r in all_records:
        yt = r["youtube_links"][0] if r["youtube_links"] else "NO LINK"
        print(f"  {r['title']} → {yt}")


if __name__ == "__main__":
    main()
