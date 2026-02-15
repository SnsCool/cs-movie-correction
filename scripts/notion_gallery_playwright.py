"""
Playwright + Chrome CDP接続でNotionギャラリービュー設定。
実行中のChromeインスタンスにDevTools Protocol経由で接続し、
ログインセッションをそのまま利用する。

前提: Chrome を --remote-debugging-port=9222 で起動済み
"""

import asyncio
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright


NEW_DB_URL = "https://www.notion.so/306f3b0fba8581dfb1d5c50fa215c62a"
CDP_URL = "http://localhost:9222"
CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)


def launch_chrome_with_debugging():
    """Chromeをリモートデバッグポート付きで起動する。"""
    # 既存のChromeを一旦終了
    subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
    time.sleep(2)

    # リモートデバッグ付きで再起動（user-data-dir指定必須）
    subprocess.Popen([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        f"--user-data-dir={CHROME_USER_DATA_DIR}",
        "--no-first-run",
    ])
    time.sleep(5)
    print("Chrome をリモートデバッグモードで起動しました")


async def main():
    launch_chrome_with_debugging()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"CDP接続失敗: {e}")
            return

        print(f"Chrome に接続しました (contexts: {len(browser.contexts)})")

        # 既存のコンテキストを使う、または新しいページを作る
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        # ---- ステップ1: ページにアクセス ----
        print("\n1. ページにアクセス中...")
        await page.goto(NEW_DB_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        # ログイン確認
        body_text = await page.evaluate("document.body.innerText")
        if "無料で始める" in body_text or "ログイン" in body_text or "Log in" in body_text:
            print("ERROR: Notionにログインされていません")
            await page.screenshot(path="assets/debug_cdp_login.png")
            print("スクリーンショット: assets/debug_cdp_login.png")
            await page.close()
            return

        print("  ✅ ログイン確認OK")
        await page.screenshot(path="assets/debug_cdp_step1.png")

        # ---- ステップ2: 設定ボタンをクリック ----
        print("\n2. 設定ボタンをクリック...")

        # まずDBが表示されるまで待機
        await page.wait_for_timeout(2000)

        # 設定ボタンを探す（複数の方法）
        settings_btn = None
        for selector in [
            '[aria-label="設定"]',
            '[aria-label="View settings"]',
            '[aria-label="Settings"]',
        ]:
            count = await page.locator(selector).count()
            if count > 0:
                settings_btn = page.locator(selector).first
                print(f"  → セレクタ '{selector}' で発見")
                break

        if settings_btn is None:
            # タブをホバーして設定アイコンを表示
            tab = page.locator('[role="tab"]').first
            tab_count = await tab.count()
            if tab_count > 0:
                await tab.hover()
                await page.wait_for_timeout(1500)
                for selector in ['[aria-label="設定"]', '[aria-label="View settings"]']:
                    count = await page.locator(selector).count()
                    if count > 0:
                        settings_btn = page.locator(selector).first
                        print(f"  → ホバー後にセレクタ '{selector}' で発見")
                        break

        if settings_btn is None:
            print("  ERROR: 設定ボタンが見つかりません")
            # デバッグ: role=buttonを全部列挙
            btns = await page.evaluate("""
                () => Array.from(document.querySelectorAll('[role="button"]'))
                    .map(b => ({label: b.getAttribute('aria-label'), text: b.textContent?.substring(0,50)}))
                    .filter(b => b.label || b.text)
            """)
            for b in btns[:30]:
                print(f"    button: label='{b['label']}' text='{b['text']}'")
            await page.screenshot(path="assets/debug_cdp_no_settings.png")
            await page.close()
            return

        await settings_btn.click()
        await page.wait_for_timeout(1500)
        print("  ✅ 設定メニュー展開")
        await page.screenshot(path="assets/debug_cdp_step2.png")

        # ---- ステップ3: レイアウトをクリック ----
        print("\n3. レイアウトをクリック...")
        layout_item = page.locator('div:has-text("レイアウト")').first
        try:
            await layout_item.wait_for(state="visible", timeout=5000)
            await layout_item.click()
            await page.wait_for_timeout(2000)
            print("  ✅ レイアウトパネル展開")
        except Exception:
            # role=menuitemで試す
            layout_item2 = page.locator('[role="menuitem"]:has-text("レイアウト")').first
            await layout_item2.click()
            await page.wait_for_timeout(2000)
            print("  ✅ レイアウトパネル展開 (fallback)")

        await page.screenshot(path="assets/debug_cdp_step3.png")

        # ---- ステップ4: ギャラリーをクリック ----
        print("\n4. ギャラリーを選択中...")
        # DOM更新を待つ
        await page.wait_for_timeout(1500)

        gallery_clicked = False
        # 方法1: テキストマッチ
        gallery_locator = page.get_by_text("ギャラリー", exact=True)
        count = await gallery_locator.count()
        print(f"  'ギャラリー' テキスト数: {count}")
        if count > 0:
            try:
                await gallery_locator.first.click()
                gallery_clicked = True
                print("  ✅ ギャラリー選択完了")
            except Exception as e:
                print(f"  方法1失敗: {e}")

        if not gallery_clicked:
            # 方法2: Gallery (英語)
            gallery_en = page.get_by_text("Gallery", exact=True)
            count_en = await gallery_en.count()
            print(f"  'Gallery' テキスト数: {count_en}")
            if count_en > 0:
                try:
                    await gallery_en.first.click()
                    gallery_clicked = True
                    print("  ✅ Gallery選択完了")
                except Exception as e:
                    print(f"  方法2失敗: {e}")

        if not gallery_clicked:
            # 方法3: JavaScriptで直接クリック
            print("  方法3: JavaScriptで要素を検索...")
            result = await page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const text = el.textContent?.trim();
                        if ((text === 'ギャラリー' || text === 'Gallery') && el.offsetParent !== null) {
                            el.click();
                            return {found: true, tag: el.tagName, text: text};
                        }
                    }
                    return {found: false};
                }
            """)
            if result.get("found"):
                gallery_clicked = True
                print(f"  ✅ JS経由でクリック: {result}")
            else:
                print("  全方法失敗")

        await page.wait_for_timeout(2000)
        await page.screenshot(path="assets/debug_cdp_step4.png")

        # ---- ステップ5: 設定パネルを閉じる ----
        print("\n5. パネルを閉じる...")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1500)

        # ---- ステップ6: グループ化設定 ----
        print("\n6. グループ化設定...")
        # 設定ボタンを再度クリック
        for selector in ['[aria-label="設定"]', '[aria-label="View settings"]']:
            count = await page.locator(selector).count()
            if count > 0:
                await page.locator(selector).first.click()
                await page.wait_for_timeout(1500)
                break

        # グループをクリック
        print("7. グループをクリック...")
        group_clicked = False
        for text in ["グループ", "Group"]:
            loc = page.get_by_text(text, exact=True)
            count = await loc.count()
            if count > 0:
                try:
                    await loc.first.click()
                    await page.wait_for_timeout(1500)
                    group_clicked = True
                    print(f"  ✅ '{text}' クリック完了")
                    break
                except Exception:
                    pass

        if not group_clicked:
            # menuitem で試す
            for text in ["グループ", "Group"]:
                loc = page.locator(f'[role="menuitem"]:has-text("{text}")').first
                count = await loc.count()
                if count > 0:
                    await loc.click()
                    await page.wait_for_timeout(1500)
                    group_clicked = True
                    print(f"  ✅ menuitem '{text}' クリック完了")
                    break

        await page.screenshot(path="assets/debug_cdp_step6.png")

        # ---- ステップ7: タグを選択 ----
        print("\n8. タグを選択...")
        await page.wait_for_timeout(1000)
        tag_clicked = False
        for text in ["タグ", "Tags"]:
            loc = page.get_by_text(text, exact=True)
            count = await loc.count()
            if count > 0:
                try:
                    await loc.first.click()
                    tag_clicked = True
                    print(f"  ✅ '{text}' でグループ化設定完了")
                    break
                except Exception:
                    pass

        if not tag_clicked:
            for text in ["タグ", "Tags"]:
                loc = page.locator(f'[role="option"]:has-text("{text}")').first
                count = await loc.count()
                if count > 0:
                    await loc.click()
                    tag_clicked = True
                    print(f"  ✅ option '{text}' でグループ化設定完了")
                    break

        await page.wait_for_timeout(2000)
        await page.screenshot(path="assets/debug_cdp_final.png")
        print("\n最終スクリーンショット: assets/debug_cdp_final.png")

        print("\n完了！")
        await page.wait_for_timeout(3000)
        await page.close()


if __name__ == "__main__":
    asyncio.run(main())
