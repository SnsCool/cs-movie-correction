"""
osascript + Quartz CoreGraphics でNotionギャラリービュー設定。
ChromeのJSでUI操作 + 画面座標を取得し、Quartzで実マウスクリック。
"""

import json
import subprocess
import time

from Quartz.CoreGraphics import (
    CGEventCreateMouseEvent,
    CGEventPost,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
)


def run_js(js_code: str) -> str:
    """Chrome active tab でJSを実行。"""
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "Google Chrome" to execute front window\'s'
        f' active tab javascript "{escaped}"'
    )
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return r.stdout.strip()


def quartz_click(x: float, y: float):
    """Quartz CoreGraphics で画面座標にマウスクリック。"""
    point = (int(x), int(y))
    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, up)


def get_element_screen_coords(js_selector_code: str) -> tuple[float, float] | None:
    """JS式でviewport座標を取得し、画面座標に変換。"""
    js = f"""(function() {{
        var el = ({js_selector_code});
        if (!el) return 'null';
        var rect = el.getBoundingClientRect();
        return JSON.stringify({{
            cx: rect.x + rect.width/2,
            cy: rect.y + rect.height/2,
            dpr: window.devicePixelRatio,
            screenX: window.screenX,
            screenY: window.screenY,
            outerHeight: window.outerHeight,
            innerHeight: window.innerHeight
        }});
    }})()"""
    result = run_js(js)
    if not result or result == "null":
        return None
    data = json.loads(result)
    dpr = data["dpr"]

    # Chrome toolbar height (screen pixels)
    # outerHeight is in CSS pixels, innerHeight is in CSS pixels
    # physical outer = outerHeight * dpr (approximately, since window frame isn't scaled)
    # Actually, on macOS: screenY gives the window's top (below menu bar)
    # The toolbar area = outerHeight - innerHeight (in CSS) * dpr => too small

    # Use fixed estimate: macOS Chrome toolbar ≈ 72 screen px
    toolbar_h = 72

    screen_x = data["screenX"] + data["cx"] * dpr
    screen_y = data["screenY"] + toolbar_h + data["cy"] * dpr
    return screen_x, screen_y


def main():
    print("=" * 50)
    print("Notion ギャラリービュー設定 (Quartz Click)")
    print("=" * 50)

    # Chromeをアクティブに
    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
    time.sleep(1)

    # Step 1: 設定ボタンをクリック (JSで十分)
    print("\n1. 設定ボタンをクリック...")
    r = run_js('document.querySelector("[aria-label=\\"設定\\"]").click(); "OK"')
    print(f"   → {r}")
    time.sleep(2)

    # Step 2: レイアウトをクリック (JSで十分)
    print("\n2. レイアウトをクリック...")
    r = run_js("""(function() {
        var items = document.querySelectorAll('[role=menuitem]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.indexOf('レイアウト') >= 0) {
                items[i].click();
                return 'OK';
            }
        }
        return 'NOT_FOUND';
    })()""")
    print(f"   → {r}")
    time.sleep(2)

    # Step 3: ギャラリーをQuartzクリック (画面座標)
    print("\n3. ギャラリーの座標を取得...")
    selector = """(function() {
        var btns = document.querySelectorAll('[role=button]');
        for (var i = 0; i < btns.length; i++) {
            if (btns[i].textContent.trim() === 'ギャラリー' && btns[i].offsetParent !== null) {
                return btns[i];
            }
        }
        return null;
    })()"""
    coords = get_element_screen_coords(selector)
    if coords:
        print(f"   → 画面座標: ({coords[0]:.0f}, {coords[1]:.0f})")
        print("   → Quartzクリック実行...")
        quartz_click(coords[0], coords[1])
        time.sleep(3)

        # 結果確認
        r = run_js("""(function() {
            return 'gallery=' + (document.querySelector('.notion-gallery-view') !== null)
                + ' table=' + (document.querySelector('.notion-table-view') !== null);
        })()""")
        print(f"   → 結果: {r}")
    else:
        print("   → ギャラリーボタンが見つかりません")
        # デバッグ: 現在のページ状態
        r = run_js("""(function() {
            var btns = document.querySelectorAll('[role=button]');
            var texts = [];
            for (var i = 0; i < btns.length && i < 20; i++) {
                var t = btns[i].textContent.trim().substring(0,20);
                if (t && btns[i].offsetParent !== null) texts.push(t);
            }
            return texts.join(' | ');
        })()""")
        print(f"   → 可視ボタン: {r}")
        return

    # Step 4: パネルを閉じる
    print("\n4. パネルを閉じる...")
    run_js("""(function() {
        var close = document.querySelector('[aria-label="閉じる"]');
        if (close) close.click();
    })()""")
    time.sleep(1)

    # Step 5: 設定→グループ
    print("\n5. 設定ボタンを再クリック...")
    run_js('document.querySelector("[aria-label=\\"設定\\"]").click(); "OK"')
    time.sleep(2)

    print("\n6. グループをクリック...")
    r = run_js("""(function() {
        var items = document.querySelectorAll('[role=menuitem]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.indexOf('グループ') >= 0) {
                items[i].click();
                return 'OK';
            }
        }
        return 'NOT_FOUND';
    })()""")
    print(f"   → {r}")
    time.sleep(2)

    # Step 6: タグを選択
    print("\n7. タグを選択...")
    # まずrole=optionで試す
    selector2 = """(function() {
        var opts = document.querySelectorAll('[role=option]');
        for (var i = 0; i < opts.length; i++) {
            if (opts[i].textContent.indexOf('タグ') >= 0) return opts[i];
        }
        var divs = document.querySelectorAll('div');
        for (var j = 0; j < divs.length; j++) {
            if (divs[j].textContent.trim() === 'タグ' && divs[j].offsetParent !== null) return divs[j];
        }
        return null;
    })()"""
    coords2 = get_element_screen_coords(selector2)
    if coords2:
        print(f"   → 画面座標: ({coords2[0]:.0f}, {coords2[1]:.0f})")
        quartz_click(coords2[0], coords2[1])
        print("   → クリック完了")
    else:
        # JSクリックで試す
        r = run_js("""(function() {
            var opts = document.querySelectorAll('[role=option]');
            for (var i = 0; i < opts.length; i++) {
                if (opts[i].textContent.indexOf('タグ') >= 0) {
                    opts[i].click();
                    return 'CLICKED';
                }
            }
            return 'NOT_FOUND';
        })()""")
        print(f"   → JS fallback: {r}")

    time.sleep(3)
    print("\n✅ 完了！")


if __name__ == "__main__":
    main()
