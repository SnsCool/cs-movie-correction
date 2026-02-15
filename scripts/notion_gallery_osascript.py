"""
macOS osascript (AppleScript) 経由でChrome上のNotionページを操作。
既存のChromeセッション（ログイン済み）を利用して
ギャラリービュー設定＋タググループ化を行う。
"""

import subprocess
import time


NEW_DB_URL = "https://www.notion.so/306f3b0fba8581dfb1d5c50fa215c62a"


def run_js_in_chrome(js_code: str) -> str:
    """Chrome のアクティブタブでJavaScriptを実行する。"""
    # エスケープ処理
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    applescript = f'''
    tell application "Google Chrome"
        set result to execute front window's active tab javascript "{escaped}"
        return result
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", applescript],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr.strip()}"
    return result.stdout.strip()


def open_url_in_chrome(url: str):
    """ChromeでURLを開く。"""
    applescript = f'''
    tell application "Google Chrome"
        activate
        if (count of windows) = 0 then
            make new window
        end if
        set URL of active tab of front window to "{url}"
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript], capture_output=True)


def wait_and_check(msg: str, seconds: int = 3):
    """待機しつつメッセージを表示。"""
    print(f"  ⏳ {msg} ({seconds}秒待機)")
    time.sleep(seconds)


def main():
    print("=" * 60)
    print("Notion ギャラリービュー設定 (osascript)")
    print("=" * 60)

    # ステップ1: URLを開く
    print("\n1. NotionページをChromeで開く...")
    open_url_in_chrome(NEW_DB_URL)
    wait_and_check("ページ読み込み", 6)

    # ログイン確認
    body = run_js_in_chrome("document.body.innerText.substring(0, 500)")
    if "Log in" in body or "ログイン" in body or "無料で始める" in body:
        print("  ERROR: ログインされていません")
        print(f"  ページテキスト: {body[:200]}")
        return
    print("  ✅ ログイン確認OK")

    # ステップ2: 設定ボタンをクリック
    print("\n2. 設定ボタンをクリック...")
    result = run_js_in_chrome("""
        (function() {
            var btn = document.querySelector('[aria-label="設定"]')
                || document.querySelector('[aria-label="View settings"]');
            if (!btn) {
                // タブにホバーイベントを発火してアイコンを表示
                var tab = document.querySelector('[role="tab"]');
                if (tab) {
                    tab.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                    tab.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                }
                return 'NEED_HOVER';
            }
            btn.click();
            return 'CLICKED';
        })()
    """)
    print(f"  結果: {result}")

    if result == "NEED_HOVER":
        wait_and_check("ホバー後に再試行", 2)
        result = run_js_in_chrome("""
            (function() {
                var btn = document.querySelector('[aria-label="設定"]')
                    || document.querySelector('[aria-label="View settings"]');
                if (btn) { btn.click(); return 'CLICKED'; }
                return 'NOT_FOUND';
            })()
        """)
        print(f"  再試行結果: {result}")

    if "NOT_FOUND" in result or "ERROR" in result:
        print("  ERROR: 設定ボタンが見つかりません")
        # デバッグ情報
        debug = run_js_in_chrome("""
            (function() {
                var btns = document.querySelectorAll('[role=button]');
                var info = [];
                btns.forEach(function(b, i) {
                    if (i < 30) {
                        info.push(b.getAttribute('aria-label') + ':' + (b.textContent || '').substring(0,30));
                    }
                });
                return info.join(' | ');
            })()
        """)
        print(f"  ボタン一覧: {debug}")
        return

    wait_and_check("設定メニュー展開", 2)

    # ステップ3: レイアウトをクリック
    print("\n3. レイアウトをクリック...")
    result = run_js_in_chrome("""
        (function() {
            // role=menuitemからレイアウトを探す
            var items = document.querySelectorAll('[role="menuitem"]');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.indexOf('レイアウト') >= 0 ||
                    items[i].textContent.indexOf('Layout') >= 0) {
                    items[i].click();
                    return 'CLICKED:' + items[i].textContent.substring(0, 30);
                }
            }
            // fallback: テキストで検索
            var allDivs = document.querySelectorAll('div');
            for (var j = 0; j < allDivs.length; j++) {
                var text = allDivs[j].textContent.trim();
                if (text === 'レイアウト' || text === 'Layout') {
                    allDivs[j].click();
                    return 'CLICKED_DIV:' + text;
                }
            }
            return 'NOT_FOUND';
        })()
    """)
    print(f"  結果: {result}")
    wait_and_check("レイアウトパネル展開", 2)

    # ステップ4: ギャラリーを選択
    print("\n4. ギャラリーを選択...")
    result = run_js_in_chrome("""
        (function() {
            // まずrole=optionで探す
            var options = document.querySelectorAll('[role="option"]');
            for (var i = 0; i < options.length; i++) {
                var text = options[i].textContent.trim();
                if (text.indexOf('ギャラリー') >= 0 || text.indexOf('Gallery') >= 0) {
                    options[i].click();
                    return 'CLICKED_OPTION:' + text;
                }
            }
            // 全divから探す（部分一致）
            var allEls = document.querySelectorAll('div, span, button');
            for (var j = 0; j < allEls.length; j++) {
                var t = allEls[j].textContent.trim();
                if ((t === 'ギャラリー' || t === 'Gallery') && allEls[j].offsetParent !== null) {
                    allEls[j].click();
                    return 'CLICKED_EL:' + t;
                }
            }
            // 存在する選択肢をリストアップ
            var optTexts = [];
            options.forEach(function(o) { optTexts.push(o.textContent.trim().substring(0, 30)); });
            return 'NOT_FOUND options=[' + optTexts.join(', ') + ']';
        })()
    """)
    print(f"  結果: {result}")
    wait_and_check("ギャラリー適用", 3)

    # ステップ5: パネルを閉じる
    print("\n5. パネルを閉じる...")
    run_js_in_chrome("""
        (function() {
            var close = document.querySelector('[aria-label="閉じる"]')
                || document.querySelector('[aria-label="Close"]');
            if (close) { close.click(); return 'CLOSED'; }
            // Escapeキーイベント
            document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27}));
            return 'ESCAPE_SENT';
        })()
    """)
    wait_and_check("パネルクローズ", 2)

    # ステップ6: グループ化設定
    print("\n6. 設定ボタンを再クリック...")
    run_js_in_chrome("""
        (function() {
            var btn = document.querySelector('[aria-label="設定"]')
                || document.querySelector('[aria-label="View settings"]');
            if (btn) { btn.click(); return 'CLICKED'; }
            return 'NOT_FOUND';
        })()
    """)
    wait_and_check("設定メニュー展開", 2)

    # ステップ7: グループをクリック
    print("\n7. グループをクリック...")
    result = run_js_in_chrome("""
        (function() {
            var items = document.querySelectorAll('[role="menuitem"]');
            for (var i = 0; i < items.length; i++) {
                var text = items[i].textContent.trim();
                if (text.indexOf('グループ') >= 0 || text === 'Group') {
                    items[i].click();
                    return 'CLICKED:' + text;
                }
            }
            var allDivs = document.querySelectorAll('div');
            for (var j = 0; j < allDivs.length; j++) {
                var t = allDivs[j].textContent.trim();
                if (t === 'グループ' || t === 'Group') {
                    allDivs[j].click();
                    return 'CLICKED_DIV:' + t;
                }
            }
            return 'NOT_FOUND';
        })()
    """)
    print(f"  結果: {result}")
    wait_and_check("グループパネル展開", 2)

    # ステップ8: タグを選択
    print("\n8. タグを選択...")
    result = run_js_in_chrome("""
        (function() {
            var options = document.querySelectorAll('[role="option"]');
            for (var i = 0; i < options.length; i++) {
                var text = options[i].textContent.trim();
                if (text.indexOf('タグ') >= 0 || text === 'Tags') {
                    options[i].click();
                    return 'CLICKED:' + text;
                }
            }
            var allEls = document.querySelectorAll('div, span');
            for (var j = 0; j < allEls.length; j++) {
                var t = allEls[j].textContent.trim();
                if ((t === 'タグ' || t === 'Tags') && allEls[j].offsetParent !== null) {
                    allEls[j].click();
                    return 'CLICKED_EL:' + t;
                }
            }
            var optTexts = [];
            options.forEach(function(o) { optTexts.push(o.textContent.trim().substring(0, 30)); });
            return 'NOT_FOUND options=[' + optTexts.join(', ') + ']';
        })()
    """)
    print(f"  結果: {result}")
    wait_and_check("グループ化適用", 3)

    print("\n" + "=" * 60)
    print("完了！Notion UIで結果を確認してください。")
    print("=" * 60)


if __name__ == "__main__":
    main()
