"""Notion UIのギャラリー設定でカードプレビューをページカバー画像に変更"""

import subprocess
import time
import json


NOTION_URL = "https://www.notion.so/306f3b0fba858000bc41eaed2d834e21"


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


def main():
    print("=== カードプレビュー設定 ===\n")

    # まずページを開き直す（設定パネルが閉じている可能性があるため）
    print("Step 1: ページを開く...")
    open_url(NOTION_URL)
    time.sleep(8)

    # Step 2: 設定アイコン（歯車）をクリック
    print("\nStep 2: 設定アイコンをクリック...")
    result = run_js(
        r"""(function() {
        // aria-label="設定" のボタンを探す
        var buttons = document.querySelectorAll('[role="button"], button');
        for (var i = 0; i < buttons.length; i++) {
            var ariaLabel = buttons[i].getAttribute('aria-label') || '';
            if (ariaLabel === '設定' || ariaLabel === 'View options' || ariaLabel === 'Settings') {
                buttons[i].click();
                return 'CLICKED: ' + ariaLabel;
            }
        }
        // 「新規」ボタンの左隣のアイコンを探す
        var newBtn = null;
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim() === '新規') {
                newBtn = buttons[i];
                break;
            }
        }
        if (!newBtn) return 'NEW_BTN_NOT_FOUND';
        var rect = newBtn.getBoundingClientRect();
        var candidates = [];
        buttons.forEach(function(b) {
            var r = b.getBoundingClientRect();
            if (Math.abs(r.y - rect.y) < 20 && r.x < rect.x && b.offsetParent !== null) {
                var text = b.textContent.trim();
                if (!text || text.length < 5) {
                    candidates.push({el: b, x: r.x, text: text || 'ICON'});
                }
            }
        });
        if (candidates.length > 0) {
            candidates.sort(function(a, b) { return b.x - a.x; });
            candidates[0].el.click();
            return 'CLICKED_NEAR_NEW: ' + candidates[0].text;
        }
        return 'NOT_FOUND';
    })()"""
    )
    print(f"  結果: {result}")
    time.sleep(2)

    # Step 3: 設定パネルの内容を確認
    print("\nStep 3: 設定パネル確認...")
    panel = run_js(
        r"""(function() {
        var items = [];
        document.querySelectorAll('[class*="overlay"], [class*="popover"], [role="dialog"], [class*="panel"]').forEach(function(c) {
            c.querySelectorAll('*').forEach(function(el) {
                if (el.children.length <= 2 && el.offsetParent !== null) {
                    var text = el.textContent.trim();
                    if (text && text.length < 50 && items.indexOf(text) === -1) {
                        items.push(text);
                    }
                }
            });
        });
        return JSON.stringify(items.slice(0, 30));
    })()"""
    )
    print(f"  パネル内容: {panel[:600]}")

    # Step 4: 「レイアウト」をクリックして展開
    print("\nStep 4: レイアウトをクリック...")
    result = run_js(
        r"""(function() {
        var all = document.querySelectorAll('div, span, button, [role="button"]');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = el.textContent.trim();
            // 「レイアウト」単独のテキスト or 「レイアウトギャラリー」を含む要素
            if (el.offsetParent !== null && el.children.length <= 3) {
                if (text === 'レイアウト' || text === 'Layout' ||
                    text === 'レイアウトギャラリー' || text === 'Layoutギャラリー') {
                    var rect = el.getBoundingClientRect();
                    // 設定パネル内（x > 1600 くらい）の要素のみ
                    if (rect.x > 1000) {
                        el.click();
                        return 'CLICKED: ' + text + ' at x=' + rect.x + ' y=' + rect.y;
                    }
                }
            }
        }
        return 'NOT_FOUND';
    })()"""
    )
    print(f"  結果: {result}")
    time.sleep(2)

    # Step 5: 展開後のメニューを確認
    print("\nStep 5: レイアウト展開後のメニュー...")
    expanded = run_js(
        r"""(function() {
        var items = [];
        document.querySelectorAll('[class*="overlay"], [class*="popover"], [role="dialog"], [class*="panel"]').forEach(function(c) {
            c.querySelectorAll('*').forEach(function(el) {
                if (el.children.length <= 2 && el.offsetParent !== null) {
                    var text = el.textContent.trim();
                    var rect = el.getBoundingClientRect();
                    if (text && text.length < 50 && text.length > 0) {
                        var key = text + '|' + Math.round(rect.x) + '|' + Math.round(rect.y);
                        if (items.indexOf(key) === -1) {
                            items.push(key);
                        }
                    }
                }
            });
        });
        return JSON.stringify(items.slice(0, 40));
    })()"""
    )
    print(f"  メニュー: {expanded[:800]}")

    # Step 6: 「カードプレビュー」をクリック
    print("\nStep 6: カードプレビューをクリック...")
    result = run_js(
        r"""(function() {
        var all = document.querySelectorAll('div, span, button, [role="button"]');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = el.textContent.trim();
            if (el.offsetParent !== null) {
                if (text === 'カードプレビュー' || text === 'Card preview' ||
                    text.indexOf('カードプレビュー') === 0) {
                    if (el.children.length <= 3) {
                        el.click();
                        return 'CLICKED: ' + text;
                    }
                }
            }
        }
        return 'NOT_FOUND';
    })()"""
    )
    print(f"  結果: {result}")
    time.sleep(2)

    # Step 7: 「ページカバー画像」を選択
    print("\nStep 7: ページカバー画像を選択...")
    # まずメニュー内容確認
    menu = run_js(
        r"""(function() {
        var items = [];
        document.querySelectorAll('[class*="overlay"], [class*="popover"], [role="dialog"], [role="listbox"], [role="menu"], [class*="dropdown"]').forEach(function(c) {
            c.querySelectorAll('*').forEach(function(el) {
                if (el.children.length <= 2 && el.offsetParent !== null) {
                    var text = el.textContent.trim();
                    if (text && text.length < 50 && items.indexOf(text) === -1) {
                        items.push(text);
                    }
                }
            });
        });
        return JSON.stringify(items.slice(0, 30));
    })()"""
    )
    print(f"  メニュー内容: {menu[:500]}")

    result = run_js(
        r"""(function() {
        var all = document.querySelectorAll('div, span, button, [role="button"], [role="option"], [role="menuitem"]');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = el.textContent.trim();
            if (el.offsetParent !== null) {
                if (text === 'ページカバー画像' || text === 'Page cover' ||
                    text === 'ページカバー' || text === 'Cover') {
                    el.click();
                    return 'CLICKED: ' + text;
                }
            }
        }
        return 'NOT_FOUND';
    })()"""
    )
    print(f"  結果: {result}")
    time.sleep(2)

    # Step 8: 最終確認
    print("\nStep 8: 最終確認...")
    final = run_js(
        r"""(function() {
        var items = [];
        document.querySelectorAll('[class*="overlay"], [class*="popover"], [role="dialog"]').forEach(function(c) {
            c.querySelectorAll('*').forEach(function(el) {
                if (el.children.length <= 2 && el.offsetParent !== null) {
                    var text = el.textContent.trim();
                    if (text && text.length < 50 && items.indexOf(text) === -1) {
                        items.push(text);
                    }
                }
            });
        });
        return JSON.stringify(items.slice(0, 20));
    })()"""
    )
    print(f"  設定パネル: {final[:500]}")

    print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
