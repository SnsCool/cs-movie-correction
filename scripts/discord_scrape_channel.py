"""指定Discordチャンネルの全スレッドからYouTubeリンクを取得"""

import json
import subprocess
import time

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1425869859685924968"
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


def get_channel_name() -> str:
    return run_js(
        r"""(function() {
        var h = document.querySelector('[class*="title_"][class*="container_"] h1, [class*="channelName"]');
        if (h) return h.textContent.trim();
        var h2 = document.querySelector('h1, h2');
        if (h2) return h2.textContent.trim();
        return '';
    })()"""
    )


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


def scroll_down():
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


def click_card_by_title(target_title: str) -> str:
    escaped_title = target_title.replace("'", "\\'").replace("\\", "\\\\")
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


def get_all_numbered_titles() -> list[str]:
    """ページ上の全番号パターンタイトルを取得"""
    raw = run_js(
        r"""(function() {
        var results = [];
        var seen = {};
        document.querySelectorAll('h3, [class*="title"]').forEach(function(el) {
            var text = el.textContent.trim();
            if (text && !seen[text] && text.length < 80) {
                seen[text] = true;
                results.push(text);
            }
        });
        return JSON.stringify(results);
    })()"""
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def main():
    print("=" * 60)
    print(f"Discordチャンネル {CHANNEL_ID} スクレイピング")
    print("=" * 60)

    # チャンネルを開く
    print("\nチャンネルを開いています...")
    open_url(CHANNEL_URL)
    time.sleep(8)

    channel_name = get_channel_name()
    print(f"チャンネル名: {channel_name}")

    # 全カードを収集（上部 + スクロール + 過去の投稿）
    all_titles = []
    seen = set()

    # 上部のカード取得
    cards = get_card_titles()
    for t in cards:
        if t not in seen:
            all_titles.append(t)
            seen.add(t)
    print(f"\n上部カード: {len(cards)} 件")

    # スクロールして全カード読み込み
    print("スクロール中...")
    for i in range(20):
        scroll_down()
        time.sleep(1.5)
        cards = get_card_titles()
        new_count = 0
        for t in cards:
            if t not in seen:
                all_titles.append(t)
                seen.add(t)
                new_count += 1
        if new_count > 0:
            print(f"  スクロール {i+1}: +{new_count} 件 (計 {len(all_titles)})")
        elif i > 5:
            break

    print(f"\n全カード: {len(all_titles)} 件")
    for i, t in enumerate(all_titles):
        print(f"  {i+1:2d}. {t}")

    # 各カードをクリックしてYouTubeリンク取得
    print(f"\n各カードのYouTubeリンク取得...")
    all_records = []

    for title in all_titles:
        print(f"\n--- {title} ---")

        # チャンネルに戻る
        open_url(CHANNEL_URL)
        time.sleep(6)

        # スクロールしてカードを表示
        for _ in range(20):
            cards = get_card_titles()
            if title in cards:
                break
            scroll_down()
            time.sleep(1.5)

        # カードクリック
        result = click_card_by_title(title)
        print(f"  クリック: {result}")
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

        # 直接アクセスしてYouTubeリンク取得
        if thread_id:
            direct_url = f"https://discord.com/channels/{GUILD_ID}/{thread_id}"
            open_url(direct_url)
            time.sleep(6)

        links = get_youtube_from_thread()
        print(f"  Thread ID: {thread_id}")
        print(f"  YouTube: {links[:3]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "channel": channel_name or CHANNEL_ID,
            "thread_id": thread_id or "",
        })

    # 保存
    output = f"assets/discord_channel_{CHANNEL_ID}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)} 件")
    print(f"チャンネル: {channel_name}")
    print(f"保存先: {output}")
    print(f"{'=' * 60}")

    for r in all_records:
        yt = r["youtube_links"][0] if r["youtube_links"] else "NO LINK"
        print(f"  {r['title']} → {yt}")


if __name__ == "__main__":
    main()
