"""1on1アーカイブの各スレッドからYouTubeリンクを取得"""

import json
import subprocess
import time
import os

GUILD_ID = "1398982066682593420"
CHANNEL_ID = "1416428648482996337"
CHANNEL_URL = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}"
OUTPUT_FILE = "assets/discord_channel_1416428648482996337.json"
PROGRESS_FILE = "assets/discord_1on1_progress.json"


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


def get_card_titles():
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


def get_youtube_from_thread():
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


def get_current_url():
    return run_js("window.location.href")


def main():
    # タイトルリスト読み込み
    with open("assets/discord_1on1_titles.json", "r", encoding="utf-8") as f:
        all_titles = json.load(f)

    # 進捗読み込み（途中再開対応）
    all_records = []
    done_titles = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            all_records = json.load(f)
            done_titles = {r["title"] for r in all_records}
        print(f"途中再開: {len(done_titles)}/{len(all_titles)} 件完了済み")

    remaining = [t for t in all_titles if t not in done_titles]
    print(f"残り: {len(remaining)} 件\n")

    for idx, title in enumerate(remaining):
        print(f"[{len(done_titles)+idx+1}/{len(all_titles)}] {title}")

        # チャンネルに戻る
        open_url(CHANNEL_URL)
        time.sleep(5)

        # スクロールしてカードを表示
        found = False
        for _ in range(30):
            cards = get_card_titles()
            if title in cards:
                found = True
                break
            scroll_down()
            time.sleep(1.2)

        if not found:
            print(f"  カード未発見 → スキップ")
            all_records.append({
                "title": title,
                "youtube_links": [],
                "channel": "1on1アーカイブ",
                "thread_id": "",
            })
            continue

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
            time.sleep(5)

        links = get_youtube_from_thread()
        yt = links[0] if links else "NO LINK"
        print(f"  → {yt}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "channel": "1on1アーカイブ",
            "thread_id": thread_id or "",
        })

        # 10件ごとに進捗保存
        if (idx + 1) % 10 == 0:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(all_records, f, ensure_ascii=False, indent=2)
            print(f"  [進捗保存: {len(all_records)} 件]")

    # 最終保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    # 進捗ファイルも更新
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完了: {len(all_records)} 件")
    print(f"保存先: {OUTPUT_FILE}")
    print(f"{'=' * 60}")

    with_link = sum(1 for r in all_records if r["youtube_links"])
    no_link = sum(1 for r in all_records if not r["youtube_links"])
    print(f"YouTube有: {with_link} 件 / 無: {no_link} 件")


if __name__ == "__main__":
    main()
