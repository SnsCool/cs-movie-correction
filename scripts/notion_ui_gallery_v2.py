"""Notion UIをブラウザで操作 - ギャラリービュー設定 v2"""

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
    print("=== Notion ギャラリービュー設定 v2 ===\n")

    open_url(NOTION_URL)
    time.sleep(8)

    # Step 1: データベースのビュータブを探す
    print("Step 1: ビュータブ探索...")
    tabs = run_js(
        r"""(function() {
        var results = [];
        // Notion collection_view のタブを探す
        document.querySelectorAll('[class*="tab"], [class*="view"], [class*="boardView"], [class*="collectionView"]').forEach(function(el) {
            if (el.offsetParent !== null) {
                results.push({
                    tag: el.tagName,
                    text: el.textContent.trim().substring(0, 40),
                    class: el.className ? el.className.substring(0, 80) : '',
                    rect: el.getBoundingClientRect()
                });
            }
        });
        return JSON.stringify(results.slice(0, 20));
    })()"""
    )
    print(f"  タブ要素: {tabs[:500]}")

    # Step 2: データベースの「...」メニューボタンを探す
    print("\nStep 2: データベースメニュー探索...")
    menu_btns = run_js(
        r"""(function() {
        var results = [];
        // データベースのヘッダー付近の操作ボタンを探す
        document.querySelectorAll('[class*="collection"] [role="button"], [class*="notion-collection"] button').forEach(function(el) {
            if (el.offsetParent !== null) {
                results.push({
                    text: el.textContent.trim().substring(0, 30),
                    ariaLabel: el.getAttribute('aria-label') || '',
                    class: el.className ? el.className.substring(0, 60) : ''
                });
            }
        });
        // svg アイコンボタンも探す
        document.querySelectorAll('[class*="notion-collection_view"] svg, [class*="viewMore"]').forEach(function(el) {
            var parent = el.closest('[role="button"]') || el.parentElement;
            if (parent && parent.offsetParent !== null) {
                results.push({
                    text: 'SVG_BUTTON',
                    ariaLabel: parent.getAttribute('aria-label') || '',
                    class: parent.className ? parent.className.substring(0, 60) : ''
                });
            }
        });
        return JSON.stringify(results.slice(0, 20));
    })()"""
    )
    print(f"  メニュー: {menu_btns[:500]}")

    # Step 3: 「新規」ボタンの近くにある操作アイコンを探す
    print("\nStep 3: 「新規」ボタン付近のUI...")
    nearby = run_js(
        r"""(function() {
        var results = [];
        // 「新規」ボタンを基準にして周辺要素を探す
        var buttons = document.querySelectorAll('[role="button"]');
        var newBtn = null;
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim() === '新規') {
                newBtn = buttons[i];
                break;
            }
        }
        if (!newBtn) return JSON.stringify({error: '新規ボタンが見つかりません'});

        var rect = newBtn.getBoundingClientRect();
        results.push({text: '新規', x: rect.x, y: rect.y});

        // 同じ行（Y座標が近い）のボタンを全部取得
        buttons.forEach(function(b) {
            var r = b.getBoundingClientRect();
            if (Math.abs(r.y - rect.y) < 30 && b !== newBtn && b.offsetParent !== null) {
                results.push({
                    text: b.textContent.trim().substring(0, 20) || 'ICON',
                    x: r.x,
                    y: r.y,
                    w: r.width,
                    h: r.height,
                    ariaLabel: b.getAttribute('aria-label') || ''
                });
            }
        });

        // svgアイコンも同じ行で探す
        document.querySelectorAll('svg').forEach(function(svg) {
            var r = svg.getBoundingClientRect();
            if (Math.abs(r.y - rect.y) < 30 && r.width > 10 && r.width < 30) {
                var parent = svg.closest('[role="button"]') || svg.parentElement;
                results.push({
                    text: 'SVG',
                    x: r.x,
                    y: r.y,
                    ariaLabel: parent ? (parent.getAttribute('aria-label') || '') : ''
                });
            }
        });

        return JSON.stringify(results);
    })()"""
    )
    print(f"  周辺UI: {nearby[:800]}")

    # Step 4: データベースヘッダーの「•••」や設定アイコンをクリック
    print("\nStep 4: 設定アイコンクリック...")
    result = run_js(
        r"""(function() {
        // 「新規」ボタンの左隣にあるアイコンボタンを探す
        var buttons = document.querySelectorAll('[role="button"]');
        var newBtn = null;
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim() === '新規') {
                newBtn = buttons[i];
                break;
            }
        }
        if (!newBtn) return 'NEW_BTN_NOT_FOUND';

        var rect = newBtn.getBoundingClientRect();

        // 「新規」の左側にあるアイコンボタン（設定/フィルタ等）をクリック
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

        // 最も右のアイコン（新規の直前）をクリック
        if (candidates.length > 0) {
            candidates.sort(function(a, b) { return b.x - a.x; });
            candidates[0].el.click();
            return 'CLICKED: ' + candidates[0].text + ' at x=' + candidates[0].x;
        }

        return 'NO_ICON_FOUND';
    })()"""
    )
    print(f"  結果: {result}")
    time.sleep(2)

    # メニューの内容を確認
    menu = run_js(
        r"""(function() {
        var items = [];
        // オーバーレイ/ポップオーバー内の全テキストを取得
        document.querySelectorAll('[class*="overlay"], [class*="popover"], [class*="menu"], [class*="dropdown"]').forEach(function(container) {
            container.querySelectorAll('div, span, button').forEach(function(el) {
                if (el.offsetParent !== null && el.children.length <= 2) {
                    var text = el.textContent.trim();
                    if (text && text.length < 40 && items.indexOf(text) === -1) {
                        items.push(text);
                    }
                }
            });
        });
        // role="dialog" も確認
        document.querySelectorAll('[role="dialog"], [role="menu"]').forEach(function(d) {
            d.querySelectorAll('*').forEach(function(el) {
                if (el.children.length <= 1) {
                    var text = el.textContent.trim();
                    if (text && text.length < 40 && items.indexOf(text) === -1) {
                        items.push(text);
                    }
                }
            });
        });
        return JSON.stringify(items);
    })()"""
    )
    print(f"  メニュー内容: {menu[:800]}")

    # もしメニューにレイアウト関連があればクリック
    try:
        items = json.loads(menu)
    except:
        items = []

    if "レイアウト" in items or "Layout" in items:
        print("\nStep 5: レイアウトをクリック...")
        run_js(
            r"""(function() {
            var all = document.querySelectorAll('div, span');
            for (var i = 0; i < all.length; i++) {
                var text = all[i].textContent.trim();
                if ((text === 'レイアウト' || text === 'Layout') &&
                    all[i].offsetParent !== null && all[i].children.length <= 2) {
                    all[i].click();
                    return 'CLICKED';
                }
            }
            return 'NOT_FOUND';
        })()"""
        )
        time.sleep(2)

        sub_menu = run_js(
            r"""(function() {
            var items = [];
            document.querySelectorAll('[class*="overlay"], [class*="popover"], [role="dialog"]').forEach(function(c) {
                c.querySelectorAll('*').forEach(function(el) {
                    if (el.children.length <= 1 && el.offsetParent !== null) {
                        var text = el.textContent.trim();
                        if (text && text.length < 40 && items.indexOf(text) === -1) items.push(text);
                    }
                });
            });
            return JSON.stringify(items);
        })()"""
        )
        print(f"  サブメニュー: {sub_menu[:500]}")

        # ギャラリーをクリック
        print("\nStep 6: ギャラリーをクリック...")
        run_js(
            r"""(function() {
            var all = document.querySelectorAll('div, span');
            for (var i = 0; i < all.length; i++) {
                var text = all[i].textContent.trim();
                if ((text === 'ギャラリー' || text === 'Gallery') &&
                    all[i].offsetParent !== null && all[i].children.length <= 2) {
                    all[i].click();
                    return 'CLICKED';
                }
            }
            return 'NOT_FOUND';
        })()"""
        )
        time.sleep(3)

    elif "ギャラリー" in items or "Gallery" in items:
        print("\nStep 5: 直接ギャラリーをクリック...")
        run_js(
            r"""(function() {
            var all = document.querySelectorAll('div, span');
            for (var i = 0; i < all.length; i++) {
                var text = all[i].textContent.trim();
                if ((text === 'ギャラリー' || text === 'Gallery') &&
                    all[i].offsetParent !== null && all[i].children.length <= 2) {
                    all[i].click();
                    return 'CLICKED';
                }
            }
            return 'NOT_FOUND';
        })()"""
        )
        time.sleep(3)

    print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
