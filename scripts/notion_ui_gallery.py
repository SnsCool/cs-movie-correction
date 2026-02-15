"""NotionのUIをブラウザ経由で操作してギャラリービューに変更"""

import subprocess
import time


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


def click_element_by_text(text: str, tag: str = "*") -> str:
    """テキストで要素を探してクリック"""
    escaped = text.replace("'", "\\'")
    return run_js(
        f"""(function() {{
        var all = document.querySelectorAll('{tag}');
        for (var i = 0; i < all.length; i++) {{
            if (all[i].textContent.trim() === '{escaped}' && all[i].offsetParent !== null) {{
                all[i].click();
                return 'CLICKED: ' + all[i].tagName;
            }}
        }}
        return 'NOT_FOUND';
    }})()"""
    )


def click_element_containing_text(text: str) -> str:
    """テキストを含む要素をクリック"""
    escaped = text.replace("'", "\\'")
    return run_js(
        f"""(function() {{
        var all = document.querySelectorAll('div, span, button, [role="button"], [role="menuitem"], [role="option"]');
        for (var i = 0; i < all.length; i++) {{
            var el = all[i];
            if (el.textContent.trim().indexOf('{escaped}') >= 0
                && el.offsetParent !== null
                && el.children.length <= 3) {{
                el.click();
                return 'CLICKED: ' + el.tagName + ' - ' + el.textContent.trim().substring(0, 50);
            }}
        }}
        return 'NOT_FOUND';
    }})()"""
    )


def find_and_click_view_selector() -> str:
    """ビューセレクター（テーブル/ギャラリー等）をクリック"""
    return run_js(
        r"""(function() {
        // "テーブル" ビューボタンを探す
        var buttons = document.querySelectorAll('[role="button"], button, div[class*="view"]');
        for (var i = 0; i < buttons.length; i++) {
            var text = buttons[i].textContent.trim();
            if ((text === 'テーブル' || text === 'Table' || text === 'ボード' || text === 'Board')
                && buttons[i].offsetParent !== null
                && text.length < 20) {
                buttons[i].click();
                return 'CLICKED: ' + text;
            }
        }
        // データベースヘッダー付近のドロップダウンを探す
        var headers = document.querySelectorAll('[class*="collection_view"], [class*="viewButton"]');
        for (var i = 0; i < headers.length; i++) {
            if (headers[i].offsetParent !== null) {
                headers[i].click();
                return 'CLICKED_HEADER: ' + headers[i].textContent.trim().substring(0, 30);
            }
        }
        return 'NOT_FOUND';
    })()"""
    )


def get_visible_menu_items() -> str:
    """表示中のメニュー項目を取得"""
    return run_js(
        r"""(function() {
        var items = [];
        document.querySelectorAll('[role="menuitem"], [role="option"], [class*="menu"] [role="button"]').forEach(function(el) {
            if (el.offsetParent !== null) {
                items.push(el.textContent.trim().substring(0, 40));
            }
        });
        // ポップオーバー/モーダル内のボタンも確認
        document.querySelectorAll('[class*="popover"], [class*="overlay"], [class*="modal"]').forEach(function(pop) {
            pop.querySelectorAll('div, span').forEach(function(el) {
                if (el.offsetParent !== null && el.children.length <= 1) {
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


def main():
    print("=== Notion UI操作: ギャラリービュー設定 ===\n")

    # 1. Notionページを開く
    print("1. ページを開く...")
    open_url(NOTION_URL)
    time.sleep(8)

    # 2. ページ上の要素を確認
    print("\n2. ページ上のボタン/ビュー確認...")
    buttons = run_js(
        r"""(function() {
        var results = [];
        document.querySelectorAll('[role="button"], button').forEach(function(b) {
            if (b.offsetParent !== null) {
                var text = b.textContent.trim();
                if (text && text.length < 30) {
                    results.push(text);
                }
            }
        });
        return JSON.stringify(results);
    })()"""
    )
    print(f"  ボタン: {buttons[:500]}")

    # 3. ビューセレクターをクリック
    print("\n3. ビューセレクターをクリック...")
    result = find_and_click_view_selector()
    print(f"  結果: {result}")
    time.sleep(2)

    # メニュー表示確認
    menu_items = get_visible_menu_items()
    print(f"  メニュー: {menu_items[:500]}")

    # 4. "ギャラリー"を選択
    print("\n4. ギャラリーを選択...")
    result = click_element_containing_text("ギャラリー")
    if result == "NOT_FOUND":
        result = click_element_containing_text("Gallery")
    print(f"  結果: {result}")
    time.sleep(3)

    # 5. レイアウト設定（カードプレビュー）
    print("\n5. レイアウト設定...")

    # 設定メニューを開く（•••ボタンまたは設定アイコン）
    result = run_js(
        r"""(function() {
        // ビューオプションボタン（...や設定アイコン）を探す
        var buttons = document.querySelectorAll('[role="button"], button, svg');
        for (var i = 0; i < buttons.length; i++) {
            var el = buttons[i];
            var text = el.textContent.trim();
            var ariaLabel = el.getAttribute('aria-label') || '';
            if ((ariaLabel.indexOf('View options') >= 0 ||
                 ariaLabel.indexOf('ビューオプション') >= 0 ||
                 text === '⋯' || text === '•••' ||
                 ariaLabel.indexOf('property') >= 0 ||
                 ariaLabel.indexOf('Properties') >= 0) &&
                el.offsetParent !== null) {
                el.click();
                return 'CLICKED: ' + ariaLabel + ' / ' + text;
            }
        }
        return 'NOT_FOUND';
    })()"""
    )
    print(f"  設定メニュー: {result}")
    time.sleep(2)

    menu_items = get_visible_menu_items()
    print(f"  メニュー: {menu_items[:500]}")

    # レイアウトをクリック
    result = click_element_containing_text("レイアウト")
    if result == "NOT_FOUND":
        result = click_element_containing_text("Layout")
    print(f"  レイアウト: {result}")
    time.sleep(2)

    menu_items = get_visible_menu_items()
    print(f"  メニュー: {menu_items[:500]}")

    # カードプレビューを変更
    result = click_element_containing_text("カードプレビュー")
    if result == "NOT_FOUND":
        result = click_element_containing_text("Card preview")
    print(f"  カードプレビュー: {result}")
    time.sleep(2)

    menu_items = get_visible_menu_items()
    print(f"  メニュー: {menu_items[:500]}")

    # ページカバー画像を選択
    result = click_element_containing_text("ページカバー画像")
    if result == "NOT_FOUND":
        result = click_element_containing_text("Page cover")
    print(f"  ページカバー画像: {result}")
    time.sleep(2)

    print("\n=== 完了 ===")
    print("Notionページを確認してください")


if __name__ == "__main__":
    main()
