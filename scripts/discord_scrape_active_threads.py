"""アクティブセクションの全スレッドからYouTubeリンクを取得し、Notionに追加"""

import json
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
    print("アクティブスレッド YouTubeリンク取得")
    print("=" * 60)

    # チャンネルを開く
    print("\nチャンネルを開いています...")
    open_url(CHANNEL_URL)
    time.sleep(7)

    # カード一覧を取得
    titles = get_card_titles()
    print(f"カード検出: {len(titles)} 件")
    for i, t in enumerate(titles):
        print(f"  {i}: {t}")

    # 各カードをクリックしてYouTubeリンク取得
    all_records = []
    for idx, title in enumerate(titles):
        print(f"\n[{idx+1}/{len(titles)}] {title}")

        click_card_by_index(idx)
        time.sleep(5)

        links = get_youtube_links()
        print(f"  YouTube: {links[:3]}")

        all_records.append({
            "title": title,
            "youtube_links": links,
            "tag": "マネタイズ",
            "channel": "マネタイズ動画講義",
        })

        go_back()
        time.sleep(4)

        # カードが再表示されるまで待機
        retry = 0
        while retry < 3:
            check_titles = get_card_titles()
            if len(check_titles) >= len(titles):
                break
            time.sleep(2)
            retry += 1

    # 保存
    output = "assets/discord_active_threads.json"
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
