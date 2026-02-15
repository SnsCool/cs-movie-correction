"""
Discordフォーラムの各スレッドカードをクリックしてYouTubeリンクを抽出。
osascript経由で既存Chromeセッションを利用。
"""

import json
import os
import re
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_VIDEO_DB_ID = "306f3b0f-ba85-81df-b1d5-c50fa215c62a"

CHANNELS = [
    {
        "name": "1on1アーカイブ",
        "url": "https://discord.com/channels/1398982066682593420/1416428648482996337",
        "tag": "1on1",
    },
    {
        "name": "マネタイズ動画講義",
        "url": "https://discord.com/channels/1398982066682593420/1411044183032201439",
        "tag": "マネタイズ",
    },
    {
        "name": "グルコンアーカイブ",
        "url": "https://discord.com/channels/1398982066682593420/1425869859685924968",
        "tag": "グループコンサル",
    },
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


def get_card_titles() -> list[str]:
    """フォーラムのカードタイトル一覧を取得"""
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
    """指定インデックスのカードをクリック"""
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
    """現在のページからYouTubeリンクを抽出"""
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
        // Also check for embedded video links in text
        var allText = document.body.innerText;
        var matches = allText.match(/https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[^\s]+/g);
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
    """ブラウザの戻るボタン"""
    run_js("history.back()")


def parse_date(title: str) -> str | None:
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", title)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def parse_lecturer(title: str) -> str:
    # "陸講師×Kellyさん" → "陸"
    m = re.search(r"[_｜](.+?)講師", title)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\S+?)講師", title)
    if m:
        name = m.group(1)
        name = re.sub(r"^\d{4}\.\d{1,2}\.\d{1,2}", "", name).strip("_｜ ")
        name = re.sub(r"^(グルコン|講師対談|1on1)\s*[｜_]*\s*", "", name)
        return name
    return ""


def main():
    all_records = []

    for ch in CHANNELS:
        print(f"\n{'='*60}")
        print(f"{ch['name']} ({ch['url']})")
        print(f"{'='*60}")

        open_url(ch["url"])
        time.sleep(7)

        # Check for "過去の投稿" and click
        run_js(
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
        time.sleep(2)

        titles = get_card_titles()
        print(f"  カード数: {len(titles)}")

        for idx, title in enumerate(titles):
            print(f"\n  [{idx+1}/{len(titles)}] {title[:60]}")

            # Click the card
            r = click_card_by_index(idx)
            if "CLICKED" not in r:
                print(f"    → Click failed: {r}")
                continue
            time.sleep(4)

            # Extract YouTube links
            links = get_youtube_links()
            print(f"    → Links: {links}")

            date = parse_date(title)
            lecturer = parse_lecturer(title)

            all_records.append(
                {
                    "title": title,
                    "date": date,
                    "lecturer": lecturer,
                    "tag": ch["tag"],
                    "youtube_links": links,
                    "channel": ch["name"],
                }
            )

            # Go back to forum
            go_back()
            time.sleep(3)

    # Save raw data
    with open("assets/discord_extracted.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    # Sort by date
    all_records.sort(key=lambda x: x.get("date") or "9999-99-99")

    print(f"\n{'='*60}")
    print(f"全レコード: {len(all_records)} 件（日付順）")
    print(f"{'='*60}")
    for r in all_records:
        yt = r["youtube_links"][0] if r["youtube_links"] else "NO_LINK"
        print(
            f"  {r.get('date', '????-??-??')} | {r['tag']:12s} | {r['lecturer']:8s} | {r['title'][:35]} | {yt[:50]}"
        )


if __name__ == "__main__":
    main()
