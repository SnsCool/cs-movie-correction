"""
osascript 経由で既存Chromeセッションを使い、Discordチャンネルからメッセージを抽出。
"""

import json
import subprocess
import time

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
    """Chrome active tab でJSを実行。"""
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "Google Chrome" to execute front window\'s'
        f' active tab javascript "{escaped}"'
    )
    r = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        return f"ERROR: {r.stderr.strip()}"
    return r.stdout.strip()


def open_url(url: str):
    """Chrome active tab でURLを開く。"""
    script = f'''
    tell application "Google Chrome"
        set URL of active tab of front window to "{url}"
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def extract_channel_messages() -> list:
    """現在のDiscordチャンネルから全メッセージを抽出。"""
    js = r"""
(function() {
    var msgs = document.querySelectorAll('[id^="chat-messages-"]');
    var result = [];
    var lastDate = '';

    msgs.forEach(function(el) {
        // Date divider
        var divider = el.querySelector('[class*="dividerContent"]');
        if (divider) {
            lastDate = divider.textContent.trim();
        }

        // Author
        var authorEl = el.querySelector('[class*="username_"]');
        var author = authorEl ? authorEl.textContent.trim() : '';

        // Timestamp
        var timeEl = el.querySelector('time');
        var timestamp = timeEl ? timeEl.getAttribute('datetime') : '';
        var timeText = timeEl ? timeEl.textContent.trim() : '';

        // Content
        var contentEl = el.querySelector('[id^="message-content-"]');
        var content = contentEl ? contentEl.textContent.trim() : '';

        // Links
        var links = [];
        el.querySelectorAll('a[href]').forEach(function(a) {
            var href = a.getAttribute('href');
            if (href && href.indexOf('discord.com') === -1 && href.indexOf('javascript:') !== 0) {
                links.push(href);
            }
        });

        // Embed titles (YouTube etc)
        var embedTitles = [];
        el.querySelectorAll('[class*="embedTitle"]').forEach(function(e) {
            embedTitles.push(e.textContent.trim());
        });

        // Attachments (video files etc)
        var attachments = [];
        el.querySelectorAll('[class*="attachment"] a[href]').forEach(function(a) {
            attachments.push(a.getAttribute('href'));
        });

        if (content || links.length > 0 || embedTitles.length > 0 || attachments.length > 0) {
            result.push({
                author: author,
                timestamp: timestamp,
                timeText: timeText,
                content: content.substring(0, 500),
                links: links,
                embedTitles: embedTitles,
                attachments: attachments
            });
        }
    });
    return JSON.stringify({count: result.length, messages: result});
})()
"""
    return run_js(js)


def scroll_up():
    """Discord メッセージリストを上にスクロール。"""
    js = r"""
(function() {
    // Try multiple selectors for Discord's scroller
    var scroller = document.querySelector('[data-list-id="chat-messages"]');
    if (!scroller) {
        // Try parent of messages
        var firstMsg = document.querySelector('[id^="chat-messages-"]');
        if (firstMsg) scroller = firstMsg.parentElement;
    }
    if (!scroller) {
        var main = document.querySelector('main');
        if (main) {
            var divs = main.querySelectorAll('div');
            for (var i = 0; i < divs.length; i++) {
                if (divs[i].scrollHeight > divs[i].clientHeight && divs[i].clientHeight > 200) {
                    scroller = divs[i];
                    break;
                }
            }
        }
    }
    if (scroller) {
        var before = scroller.scrollTop;
        scroller.scrollTop = 0;
        return 'scrolled from ' + before + ' to ' + scroller.scrollTop + ' (height=' + scroller.scrollHeight + ')';
    }
    return 'NO_SCROLLER';
})()
"""
    return run_js(js)


def get_page_text_summary():
    """ページのメッセージ部分のテキストを取得。"""
    js = r"""
(function() {
    var main = document.querySelector('main');
    if (!main) return 'NO_MAIN';
    return main.innerText.substring(0, 5000);
})()
"""
    return run_js(js)


def main():
    all_data = {}

    for ch in CHANNELS:
        print(f"\n{'='*60}")
        print(f"Channel: {ch['name']}")
        print(f"{'='*60}")

        # Navigate to channel
        open_url(ch["url"])
        time.sleep(6)

        # Verify we're on the right page
        title = run_js("document.title")
        print(f"  Page title: {title}")

        # Try scrolling up to load older messages
        for i in range(5):
            r = scroll_up()
            print(f"  Scroll {i+1}: {r}")
            if "NO_SCROLLER" in r:
                time.sleep(2)
            else:
                time.sleep(2)

        # Scroll back to top after loading
        scroll_up()
        time.sleep(2)

        # Extract messages
        result = extract_channel_messages()
        print(f"  Raw result length: {len(result)}")

        try:
            data = json.loads(result)
            messages = data.get("messages", [])
            all_data[ch["name"]] = {"tag": ch["tag"], "messages": messages}
            print(f"  Extracted {len(messages)} messages")
            for m in messages[:3]:
                print(
                    f"    {m.get('timestamp', '?')[:16]} | {m.get('author', '?')[:15]} | {m.get('content', '')[:60]}"
                )
            if len(messages) > 3:
                print(f"    ... and {len(messages) - 3} more")
        except json.JSONDecodeError:
            # Fallback: get page text
            print("  JSON parse failed, getting raw text...")
            text = get_page_text_summary()
            all_data[ch["name"]] = {"tag": ch["tag"], "raw_text": text}
            print(f"  Raw text: {text[:300]}")

    # Save results
    with open("assets/discord_messages.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved to assets/discord_messages.json")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for ch_name, data in all_data.items():
        msgs = data.get("messages", [])
        print(f"\n{ch_name} (tag={data.get('tag', '?')}):")
        if msgs:
            for m in msgs:
                ts = m.get("timestamp", "")[:10]
                author = m.get("author", "不明")
                content = m.get("content", "")[:80]
                links = m.get("links", [])
                print(f"  {ts} | {author} | {content}")
                for link in links:
                    print(f"    → {link}")
        elif "raw_text" in data:
            print(f"  (raw text available)")


if __name__ == "__main__":
    main()
