"""
Browser Use の BrowserSession を直接使用（Agent不使用）。
Chrome プロファイルでログインセッション利用 → Playwright で直接操作。
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use import BrowserProfile, BrowserSession

NEW_DB_URL = "https://www.notion.so/306f3b0fba8581dfb1d5c50fa215c62a"
CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)


async def main():
    profile = BrowserProfile(
        user_data_dir=CHROME_USER_DATA_DIR,
        headless=False,
        window_size={"width": 1400, "height": 900},
    )

    session = BrowserSession(browser_profile=profile)
    await session.start()

    page = await session.get_current_page()
    print(f"ブラウザ起動OK (page: {page is not None})")

    # Step 1: ページにアクセス
    print("\n1. ページにアクセス中...")
    await page.goto(NEW_DB_URL, timeout=30000)
    await page.wait_for_timeout(5000)

    # ログイン確認
    body = await page.evaluate("document.body.innerText.substring(0, 300)")
    if "Log in" in body or "無料で始める" in body:
        print("ERROR: ログインされていません")
        await session.stop()
        return
    print("  ✅ ログイン確認OK")

    # Step 2: 設定ボタンをクリック
    print("\n2. 設定ボタンをクリック...")
    settings = page.locator('[aria-label="設定"]').first
    await settings.click(timeout=10000)
    await page.wait_for_timeout(2000)
    print("  ✅ 設定メニュー展開")

    # Step 3: レイアウトをクリック
    print("\n3. レイアウトをクリック...")
    layout = page.locator('[role="menuitem"]').filter(has_text="レイアウト").first
    await layout.click(timeout=5000)
    await page.wait_for_timeout(2000)
    print("  ✅ レイアウトパネル展開")

    # Step 4: ギャラリーをクリック
    print("\n4. ギャラリーを選択...")
    clicked = False

    # Playwright テキストセレクタ: DOM更新後も正しく要素を検出
    for attempt in range(3):
        try:
            gallery = page.locator('[role="button"]').filter(has_text="ギャラリー").first
            await gallery.click(timeout=5000)
            clicked = True
            print("  ✅ ギャラリー選択完了")
            break
        except Exception as e:
            print(f"  試行{attempt+1}: {e}")
            await page.wait_for_timeout(1000)

    if not clicked:
        # fallback: get_by_text
        try:
            gallery2 = page.get_by_text("ギャラリー", exact=True).first
            await gallery2.click(timeout=5000)
            clicked = True
            print("  ✅ ギャラリー選択完了 (fallback)")
        except Exception as e:
            print(f"  全試行失敗: {e}")
            await page.screenshot(path="assets/debug_gallery_fail.png")
            await session.stop()
            return

    await page.wait_for_timeout(3000)

    # Step 5: パネルを閉じる
    print("\n5. パネルを閉じる...")
    try:
        close = page.locator('[aria-label="閉じる"]').first
        await close.click(timeout=3000)
    except Exception:
        await page.keyboard.press("Escape")
    await page.wait_for_timeout(1500)

    # Step 6: 設定を再度開く
    print("\n6. 設定を再度開く...")
    settings2 = page.locator('[aria-label="設定"]').first
    await settings2.click(timeout=10000)
    await page.wait_for_timeout(2000)
    print("  ✅ 設定メニュー展開")

    # Step 7: グループをクリック
    print("\n7. グループをクリック...")
    group = page.locator('[role="menuitem"]').filter(has_text="グループ").first
    await group.click(timeout=5000)
    await page.wait_for_timeout(2000)
    print("  ✅ グループパネル展開")

    # Step 8: タグを選択
    print("\n8. タグを選択...")
    try:
        tag = page.locator('[role="option"]').filter(has_text="タグ").first
        await tag.click(timeout=5000)
        print("  ✅ タグでグループ化完了")
    except Exception:
        tag2 = page.get_by_text("タグ", exact=True).first
        await tag2.click(timeout=5000)
        print("  ✅ タグでグループ化完了 (fallback)")

    await page.wait_for_timeout(3000)

    # 最終スクリーンショット
    await page.screenshot(path="assets/debug_gallery_result.png")
    print("\n最終スクリーンショット: assets/debug_gallery_result.png")
    print("\n✅ 全ステップ完了！")

    await session.stop()


if __name__ == "__main__":
    asyncio.run(main())
