"""フォーラムページのDOM構造を調査して、全スレッドを発見する"""

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
        ["osascript", "-e", script], capture_output=True, text=True, timeout=30
    )
    return r.stdout.strip()


def open_url(url: str):
    script = f'tell application "Google Chrome" to set URL of active tab of front window to "{url}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def main():
    print("=== DOM構造調査 ===\n")

    open_url(CHANNEL_URL)
    time.sleep(8)

    # 1. 「過去の投稿」周辺の構造を調査
    print("--- 1. セクション構造 ---")
    sections = run_js(
        r"""(function() {
        var info = [];
        // 全セクションヘッダーを探す
        var allText = [];
        document.querySelectorAll('*').forEach(function(el) {
            if (el.children.length === 0 || el.children.length === 1) {
                var text = el.textContent.trim();
                if (text && text.length < 30 && text.match(/(投稿|スレッド|thread|post|active|sort|並び)/i)) {
                    info.push({tag: el.tagName, text: text, class: el.className ? el.className.substring(0, 80) : ''});
                }
            }
        });
        return JSON.stringify(info);
    })()"""
    )
    print(f"  セクション: {sections[:1000]}")

    # 2. フォーラムコンテナの構造
    print("\n--- 2. フォーラムコンテナ ---")
    container = run_js(
        r"""(function() {
        var forum = document.querySelector('[class*="forumOrHome"], [class*="forum"], [class*="channelMain"]');
        if (!forum) {
            // 全コンテナの中からフォーラムっぽいものを探す
            var containers = document.querySelectorAll('[class*="container_"], [class*="content_"]');
            for (var i = 0; i < containers.length; i++) {
                var cards = containers[i].querySelectorAll('[class*="card_"]');
                if (cards.length > 0) {
                    forum = containers[i];
                    break;
                }
            }
        }
        if (!forum) return 'NOT_FOUND';

        var sections = [];
        var children = forum.children;
        for (var i = 0; i < Math.min(children.length, 20); i++) {
            var child = children[i];
            var cardCount = child.querySelectorAll('[class*="card_"][class*="mainCard"]').length;
            sections.push({
                tag: child.tagName,
                class: child.className ? child.className.substring(0, 60) : '',
                text: child.textContent.trim().substring(0, 50),
                cards: cardCount
            });
        }
        return JSON.stringify(sections);
    })()"""
    )
    print(f"  コンテナ: {container[:1500]}")

    # 3. スクロール可能なエリアの全カードを調査
    print("\n--- 3. 全カード（スクロール前後） ---")

    # まず上部にスクロール
    run_js(
        r"""(function() {
        var containers = document.querySelectorAll('[class*="scrollerBase_"], [class*="scroller_"]');
        containers.forEach(function(c) {
            c.scrollTop = 0;
        });
    })()"""
    )
    time.sleep(2)

    top_cards = run_js(
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
    print(f"  上部のカード: {top_cards}")

    # スクロールしていく
    for i in range(10):
        run_js(
            r"""(function() {
            var containers = document.querySelectorAll('[class*="scrollerBase_"], [class*="scroller_"]');
            containers.forEach(function(c) {
                c.scrollTop += 500;
            });
        })()"""
        )
        time.sleep(1)

    bottom_cards = run_js(
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
    print(f"  スクロール後のカード: {bottom_cards}")

    # 4. 「過去の投稿」ラベルの位置と前後のカード
    print("\n--- 4. 「過去の投稿」ラベルの位置 ---")
    past_posts_info = run_js(
        r"""(function() {
        var result = {};
        var allDivs = document.querySelectorAll('div, span, h2, h3');
        for (var i = 0; i < allDivs.length; i++) {
            if (allDivs[i].textContent.trim() === '過去の投稿') {
                result.found = true;
                result.tag = allDivs[i].tagName;
                result.class = allDivs[i].className ? allDivs[i].className.substring(0, 80) : '';

                // 親要素の構造
                var parent = allDivs[i].parentElement;
                if (parent) {
                    result.parentTag = parent.tagName;
                    result.parentClass = parent.className ? parent.className.substring(0, 80) : '';

                    // 同レベルの兄弟要素
                    var siblings = parent.parentElement ? parent.parentElement.children : [];
                    result.siblingCount = siblings.length;
                    var siblingInfo = [];
                    for (var j = 0; j < Math.min(siblings.length, 10); j++) {
                        var s = siblings[j];
                        var sCards = s.querySelectorAll('[class*="card_"][class*="mainCard"]').length;
                        siblingInfo.push({
                            tag: s.tagName,
                            text: s.textContent.trim().substring(0, 30),
                            cards: sCards
                        });
                    }
                    result.siblings = siblingInfo;
                }
                break;
            }
        }
        if (!result.found) result = {found: false};
        return JSON.stringify(result);
    })()"""
    )
    print(f"  位置情報: {past_posts_info[:1000]}")

    # 5. 全ての動画番号パターンを含むテキスト要素
    print("\n--- 5. 動画番号パターンの全テキスト ---")
    numbered = run_js(
        r"""(function() {
        var results = [];
        var seen = {};
        document.querySelectorAll('*').forEach(function(el) {
            if (el.children.length <= 2) {
                var text = el.textContent.trim();
                var match = text.match(/^([0-9]+-[0-9]+)[_ ]/);
                if (match && !seen[text] && text.length < 60) {
                    seen[text] = true;
                    results.push({
                        num: match[1],
                        text: text,
                        tag: el.tagName,
                        visible: el.offsetParent !== null
                    });
                }
            }
        });
        results.sort(function(a, b) { return a.num.localeCompare(b.num); });
        return JSON.stringify(results);
    })()"""
    )
    print(f"  番号テキスト: {numbered[:2000]}")


if __name__ == "__main__":
    main()
