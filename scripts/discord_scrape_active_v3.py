"""アクティブセクション（上部）のスレッドThread IDとYouTubeリンクを取得

1. チャンネルを開く
2. 上部のアクティブセクションのカードを取得（「過去の投稿」をクリックしない）
3. 各カードをクリックしてThread IDとYouTubeリンクを取得
"""

import json
import subprocess
import time

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1411044183032201439"
CHANNEL_URL = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}"

# 既存のNotionレコード（これらは「過去の投稿」にある）
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


def get_card_titles_filtered() -> list[str]:
    """アクティブセクションのカードのみ取得（既存タイトルを除外）"""
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
        all_titles = json.loads(raw)
        # 既存タイトルを含むカードは除外
        return [t for t in all_titles if t not in EXISTING_TITLES]
    except json.JSONDecodeError:
        return []


def get_all_card_titles() -> list[str]:
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
    """タイトルで指定してカードをクリック"""
    escaped_title = target_title.replace("'", "\\'")
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
        var msgs = document.querySelectorAll('[class*="messageContent_"], [class*="message_"], [id*="message-content"]');
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


def collapse_past_posts():
    """「過去の投稿」セクションを折りたたむ（表示されている場合）"""
    run_js(
        r"""(function() {
        var divs = document.querySelectorAll('div');
        for (var i = 0; i < divs.length; i++) {
            var text = divs[i].textContent.trim();
            if (text === '過去の投稿' && divs[i].offsetParent !== null) {
                // クリックして折りたたむ
                divs[i].click();
                return 'COLLAPSED';
            }
        }
        return 'NOT_FOUND';
    })()"""
    )


def main():
    print("=" * 60)
    print("アクティブセクション スレッド取得 v3")
    print("=" * 60)

    # チャンネルを開く
    print("\nチャンネルを開いています...")
    open_url(CHANNEL_URL)
    time.sleep(8)

    # 全カード確認
    all_cards = get_all_card_titles()
    print(f"\n表示中のカード: {len(all_cards)} 件")
    for t in all_cards:
        marker = "  [既存]" if t in EXISTING_TITLES else "  [NEW]"
        print(f"  {marker} {t}")

    # 新規カードのみ
    new_cards = [t for t in all_cards if t not in EXISTING_TITLES]
    print(f"\n新規カード: {len(new_cards)} 件")

    if not new_cards:
        print("\n新規カードが見つかりません。「過去の投稿」を折りたたんで再試行...")
        collapse_past_posts()
        time.sleep(3)
        all_cards = get_all_card_titles()
        new_cards = [t for t in all_cards if t not in EXISTING_TITLES]
        print(f"再試行後: {len(new_cards)} 件")

    if not new_cards:
        print("\nまだ見つかりません。ページをリロードして上部を確認...")
        open_url(CHANNEL_URL)
        time.sleep(8)

        # スクロールしないで上部のみ確認
        all_cards = get_all_card_titles()
        new_cards = [t for t in all_cards if t not in EXISTING_TITLES]
        print(f"リロード後: {len(new_cards)} 件")
        for t in all_cards:
            marker = "  [NEW]" if t not in EXISTING_TITLES else "  [既存]"
            print(f"  {marker} {t}")

    # 各新規カードをクリックしてThread IDとYouTubeリンクを取得
    all_records = []

    for title in new_cards:
        print(f"\n--- {title} ---")

        # チャンネルに戻る
        open_url(CHANNEL_URL)
        time.sleep(6)

        # カードクリック
        result = click_card_by_title(title)
        print(f"  クリック: {result}")

        if result != "CLICKED":
            print(f"  スキップ: カードが見つかりません")
            continue

        time.sleep(5)

        # Thread ID取得
        url = get_current_url()
        parts = url.rstrip("/").split("/")
        thread_id = None

        if "threads" in parts:
            thread_idx = parts.index("threads")
            if thread_idx + 1 < len(parts):
                thread_id = parts[thread_idx + 1]
        elif len(parts) >= 5 and parts[-1] != CHANNEL_ID:
            thread_id = parts[-1]

        print(f"  Thread ID: {thread_id}")

        # YouTubeリンク取得（スレッドページで）
        if thread_id:
            # 直接スレッドURLに再アクセス（確実なリンク取得のため）
            thread_url = f"https://discord.com/channels/{GUILD_ID}/{thread_id}"
            open_url(thread_url)
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

    # 1-1は既知なので手動追加（既にThread IDとYouTubeリンク確認済み）
    found_titles = {r["title"] for r in all_records}
    if "1-1 _基礎_Instagram収益化の全体像" not in found_titles:
        print("\n--- 1-1 _基礎_Instagram収益化の全体像 (手動追加) ---")
        # 確認のため直接アクセス
        open_url(f"https://discord.com/channels/{GUILD_ID}/1414684672180359249")
        time.sleep(6)
        links = get_youtube_from_thread()
        print(f"  YouTube: {links[:3]}")
        all_records.append({
            "title": "1-1 _基礎_Instagram収益化の全体像",
            "youtube_links": links if links else ["https://youtu.be/Rw7tXxKaynA"],
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
            "thread_id": "1414684672180359249",
        })

    # 保存
    output = "assets/discord_active_threads_v3.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)} 件の新規スレッド")
    print(f"保存先: {output}")
    print(f"{'=' * 60}")

    for r in all_records:
        yt = r["youtube_links"][0] if r["youtube_links"] else "NO LINK"
        print(f"  {r['title']} → {yt}")


if __name__ == "__main__":
    main()
