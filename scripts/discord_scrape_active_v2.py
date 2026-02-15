"""アクティブスレッドのThread IDを取得 → 各スレッドに直接アクセスしてYouTubeリンク取得

Phase 1: カードをクリック → URL変更でThread ID取得 → チャンネルに戻る
Phase 2: 各Thread IDに直接ナビゲート → YouTubeリンク取得
"""

import json
import subprocess
import time

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1411044183032201439"
CHANNEL_URL = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}"


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


def get_youtube_from_thread() -> list[str]:
    """スレッド内のメッセージエリアからのみYouTubeリンクを取得"""
    raw = run_js(
        r"""(function() {
        var links = [];
        // メッセージコンテンツ内のリンクのみ取得
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
            // テキスト内のURL
            var text = msg.textContent;
            var matches = text.match(/https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[^\s<>)]+/g);
            if (matches) {
                matches.forEach(function(m) {
                    if (links.indexOf(m) === -1) links.push(m);
                });
            }
        });
        // embed内のリンクも確認
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
    print("Phase 1: Thread ID 収集")
    print("=" * 60)

    # チャンネルを開く
    open_url(CHANNEL_URL)
    time.sleep(7)

    titles = get_card_titles()
    print(f"カード: {len(titles)} 件")

    thread_map = []  # [{title, thread_id}]

    for idx, title in enumerate(titles):
        print(f"\n  [{idx+1}/{len(titles)}] {title}")

        # カードクリック
        click_card_by_index(idx)
        time.sleep(3)

        # URLからthread IDを取得
        url = get_current_url()
        print(f"    URL: {url}")

        # URLの末尾部分がthread ID
        # Format: /channels/GUILD/CHANNEL/threads/THREAD_ID or /channels/GUILD/THREAD_ID
        parts = url.rstrip("/").split("/")
        thread_id = parts[-1] if parts[-1] != CHANNEL_ID else None

        if thread_id and thread_id != "threads":
            # /threads/XXXX の形式かもしれない
            if "threads" in parts:
                thread_idx = parts.index("threads")
                if thread_idx + 1 < len(parts):
                    thread_id = parts[thread_idx + 1]
            print(f"    Thread ID: {thread_id}")
            thread_map.append({"title": title, "thread_id": thread_id})
        else:
            print(f"    Thread ID 取得失敗")

        # チャンネルに戻る
        open_url(CHANNEL_URL)
        time.sleep(5)

        # カードが再表示されるまで待機
        for _ in range(5):
            check = get_card_titles()
            if len(check) >= len(titles):
                break
            time.sleep(2)

    print(f"\n\nThread ID 収集完了: {len(thread_map)} 件")
    for t in thread_map:
        print(f"  {t['title']} → {t['thread_id']}")

    # ===========================================================
    print("\n" + "=" * 60)
    print("Phase 2: 各スレッドのYouTubeリンク取得")
    print("=" * 60)

    all_records = []

    for item in thread_map:
        title = item["title"]
        thread_id = item["thread_id"]
        print(f"\n  [{title}] → thread/{thread_id}")

        # 直接スレッドにナビゲート
        thread_url = f"https://discord.com/channels/{GUILD_ID}/{thread_id}"
        open_url(thread_url)
        time.sleep(6)

        # YouTubeリンク取得
        links = get_youtube_from_thread()
        print(f"    YouTube: {links[:3]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
            "thread_id": thread_id,
        })

    # 保存
    output = "assets/discord_active_threads_v2.json"
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
