"""
Playwrightを使ってNotion動画アーカイブDBのギャラリービューで
タグによるグループ化を設定する。

永続化コンテキストを使用して、ログイン状態を保持する。
初回実行時は手動でNotionにログインが必要。
"""

import asyncio
import os
from playwright.async_api import async_playwright

NOTION_DB_URL = "https://www.notion.so/301f3b0fba85815aa696d4836fe88bb6"
SCREENSHOT_DIR = "/Users/hatakiyoto/cs-movie-correction/assets"
USER_DATA_DIR = "/Users/hatakiyoto/cs-movie-correction/.playwright-data"


async def is_logged_in(page) -> bool:
    """Notionにログイン済みかチェック（ワークスペースメンバーとして）"""
    # 方法: ページ上の全テキストから「無料で始める」を探す
    body_text = await page.evaluate("() => document.body?.innerText || ''")
    if "無料で始める" in body_text:
        print("  → 「無料で始める」ボタン検出 = 未ログイン")
        return False
    if "ログイン" in body_text and "ログアウト" not in body_text:
        print("  → 「ログイン」ボタン検出 = 未ログイン")
        return False
    # ワークスペースのサイドバーがあるか確認
    sidebar = await page.query_selector('.notion-sidebar')
    if sidebar:
        print("  → サイドバー検出 = ログイン済み")
        return True
    # 追加チェック: 編集用UIの存在
    has_new_btn = await page.locator('text="新規"').count() > 0
    has_add_btn = await page.locator('text="+ 新規"').count() > 0
    if has_new_btn or has_add_btn:
        print("  → 編集UI検出 = ログイン済み")
        return True
    print("  → ログイン状態不明、未ログインとして扱う")
    return False


async def try_find_group(page, step_name):
    """「グループ」メニュー項目を探してクリック"""
    await asyncio.sleep(1)
    group_el = page.locator('text="グループ"')
    if await group_el.count() > 0:
        print(f"  [{step_name}] 「グループ」発見！クリック中...")
        await group_el.first.click()
        await asyncio.sleep(1.5)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_group_menu.png")

        # 「なし」が選択されている場合、タグを選択
        # タグ以外に「なし」も表示されるので、正確に「タグ」を選ぶ
        tag_el = page.locator('text="タグ"')
        if await tag_el.count() > 0:
            await tag_el.first.click()
            print(f"  [{step_name}] タグでグループ化を設定しました！")
            await asyncio.sleep(2)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_done.png")
            return True
        else:
            print(f"  [{step_name}] 「タグ」が見つかりません")
    return False


async def main():
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    async with async_playwright() as p:
        # 永続化コンテキスト（ログインセッションを保持）
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            slow_mo=200,
            viewport={"width": 1400, "height": 900},
            locale="ja-JP",
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # --- ステップ1: ログイン確認 ---
        print("Notionにアクセス中...")
        await page.goto(NOTION_DB_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        if not await is_logged_in(page):
            print("\n⚠️  Notionにログインしていません")
            print("=" * 50)
            print("ブラウザが開きます。Notionにログインしてください。")
            print("ログイン後、自動的に続行します（120秒待機）")
            print("=" * 50)
            # ログインページに遷移
            await page.goto("https://www.notion.so/login", wait_until="domcontentloaded")

            # ログイン完了を待つ（最大120秒）
            logged_in = False
            for i in range(120):
                await asyncio.sleep(1)
                url = page.url
                # ログイン後はダッシュボードやワークスペースにリダイレクト
                if ("notion.so" in url
                        and "/login" not in url
                        and "signup" not in url
                        and "start" not in url):
                    # ログイン後のページが完全に読み込まれるまで少し待つ
                    await asyncio.sleep(3)
                    print(f"  ログイン検出！({i+1}秒)")
                    logged_in = True
                    break
                if i % 15 == 14:
                    print(f"  待機中... ({i+1}秒)")

            if not logged_in:
                print("タイムアウト。ログインしてからもう一度実行してください。")
                print("（次回実行時はログイン状態が保持されます）")
                await context.close()
                return

            # ログイン後、DBページに移動
            print("DBページに移動中...")
            await page.goto(NOTION_DB_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # ログイン確認
            if not await is_logged_in(page):
                print("まだログインされていません。もう一度お試しください。")
                await context.close()
                return

        print("ログイン確認OK")
        await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_logged_in.png")

        # --- ステップ2: ギャラリービュータブを探してクリック ---
        print("\nギャラリービューを探しています...")

        # ビュータブをDOM解析で探す
        view_tabs = await page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const results = [];
            for (const el of all) {
                const text = el.textContent?.trim();
                if (text && (text === 'ギャラリービュー' || text === 'Gallery view')
                    && el.children.length <= 2) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.width < 200) {
                        results.push({
                            tag: el.tagName,
                            text: text,
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            w: Math.round(rect.width),
                            h: Math.round(rect.height)
                        });
                    }
                }
            }
            return results;
        }""")
        print(f"  ビュータブ候補: {len(view_tabs)}")
        for vt in view_tabs:
            print(f"    {vt['tag']} '{vt['text']}' pos=({vt['x']},{vt['y']}) size={vt['w']}x{vt['h']}")

        gallery_tab = page.locator('text="ギャラリービュー"').first
        if await gallery_tab.count() > 0:
            await gallery_tab.click()
            print("ギャラリービューに切替")
            await asyncio.sleep(2)

        # --- ステップ3: ビュー設定を開く ---
        # 方法A: 右端のアイコン群のDOM位置を正確に取得してクリック
        print("\n=== ビュー設定アイコンを探索 ===")

        # 全DOMのうちツールバー行（y < 200）のクリック可能要素を取得
        all_toolbar = await page.evaluate("""() => {
            const all = document.querySelectorAll('div[role="button"], button, svg');
            return Array.from(all).map(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return {
                    tag: el.tagName,
                    role: el.getAttribute('role') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    text: el.textContent?.trim()?.substring(0, 40) || '',
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                    cursor: style.cursor,
                    visible: rect.width > 0 && rect.height > 0
                };
            }).filter(e => e.visible && e.y > 80 && e.y < 180);
        }""")

        print(f"  ツールバー付近の要素: {len(all_toolbar)}")
        for el in all_toolbar:
            print(f"    {el['tag']} role={el['role']} aria='{el['ariaLabel']}' "
                  f"text='{el['text'][:25]}' pos=({el['x']},{el['y']}) "
                  f"size={el['w']}x{el['h']} cursor={el['cursor']}")

        # 右端のSVGアイコン（x > 1100, 小さいサイズ）を抽出
        right_icons = [e for e in all_toolbar
                       if e['x'] > 1100 and e['w'] < 50 and e['h'] < 50]
        print(f"\n  右端の小アイコン: {len(right_icons)}")

        # 方法B: ⋯ボタンをホバーで表示
        print("\n=== ギャラリータブホバーで⋯検索 ===")
        tab_box = await gallery_tab.bounding_box()
        if tab_box:
            print(f"  タブ位置: ({tab_box['x']:.0f}, {tab_box['y']:.0f}) "
                  f"size={tab_box['width']:.0f}x{tab_box['height']:.0f}")

            # ホバー前のDOM状態を記録
            before_count = await page.evaluate(
                "() => document.querySelectorAll('div[role=\"button\"], svg').length"
            )

            await gallery_tab.hover()
            await asyncio.sleep(2)

            # ホバー後のDOM変化を検出
            after_elements = await page.evaluate("""() => {
                const all = document.querySelectorAll('div[role="button"], button, svg, [class*="ellipsis"]');
                return Array.from(all).map(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return {
                        tag: el.tagName,
                        role: el.getAttribute('role') || '',
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height),
                        opacity: style.opacity,
                        cursor: style.cursor,
                        visible: rect.width > 0 && rect.height > 0
                    };
                }).filter(e => e.visible && e.y > 80 && e.y < 180);
            }""")

            print(f"  ホバー前の要素数: {before_count}")
            print(f"  ホバー後の要素数: {len(after_elements)}")

            # タブ近辺（x: tab_x-20 ~ tab_x+tab_w+40）のクリック可能要素
            tab_nearby = [e for e in after_elements
                          if e['x'] > tab_box['x'] - 20
                          and e['x'] < tab_box['x'] + tab_box['width'] + 40
                          and e['cursor'] == 'pointer']
            print(f"  タブ近辺のポインタ要素: {len(tab_nearby)}")
            for el in tab_nearby:
                print(f"    {el['tag']} pos=({el['x']},{el['y']}) "
                      f"size={el['w']}x{el['h']} opacity={el['opacity']}")

            await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_hover_detail.png")

        # 方法C: 右側の3アイコンを正確にクリック
        # スクリーンショットから: フィルタ(≡), プロパティ(↕), 検索(Q) の3つ
        print("\n=== 右側アイコンのSVG位置で正確にクリック ===")

        svg_icons = await page.evaluate("""() => {
            const svgs = document.querySelectorAll('svg');
            return Array.from(svgs).map((svg, i) => {
                const rect = svg.getBoundingClientRect();
                const parent = svg.closest('div[role="button"]') || svg.parentElement;
                const parentRect = parent ? parent.getBoundingClientRect() : rect;
                return {
                    index: i,
                    svgX: Math.round(rect.x),
                    svgY: Math.round(rect.y),
                    svgW: Math.round(rect.width),
                    svgH: Math.round(rect.height),
                    parentX: Math.round(parentRect.x),
                    parentY: Math.round(parentRect.y),
                    parentW: Math.round(parentRect.width),
                    parentH: Math.round(parentRect.height),
                    parentRole: parent?.getAttribute('role') || '',
                    pathCount: svg.querySelectorAll('path').length
                };
            }).filter(s => s.svgY > 80 && s.svgY < 180 && s.svgX > 800);
        }""")

        print(f"  右半分のSVGアイコン: {len(svg_icons)}")
        for svg in svg_icons:
            print(f"    SVG[{svg['index']}] pos=({svg['svgX']},{svg['svgY']}) "
                  f"size={svg['svgW']}x{svg['svgH']} "
                  f"parent=({svg['parentX']},{svg['parentY']}) "
                  f"paths={svg['pathCount']}")

        # 各SVGの親要素をクリック試行
        for svg in svg_icons:
            cx = svg['parentX'] + svg['parentW'] / 2
            cy = svg['parentY'] + svg['parentH'] / 2
            print(f"\n    SVG[{svg['index']}] クリック ({cx:.0f}, {cy:.0f})...")
            await page.mouse.click(cx, cy)
            await asyncio.sleep(1.5)

            await page.screenshot(
                path=f"{SCREENSHOT_DIR}/pw_click_svg{svg['index']}.png"
            )

            # ポップアップの中身を確認
            popup_texts = await page.evaluate("""() => {
                const containers = document.querySelectorAll(
                    '[role="dialog"], [role="menu"], [role="listbox"], '
                    + '[style*="position: fixed"], [style*="position: absolute"]'
                );
                return Array.from(containers).map(c => {
                    const rect = c.getBoundingClientRect();
                    if (rect.width < 10 || rect.height < 10) return null;
                    return {
                        text: c.textContent?.substring(0, 300) || '',
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    };
                }).filter(Boolean);
            }""")

            for pt in popup_texts:
                short = pt['text'][:100].replace('\n', ' ')
                print(f"    ポップアップ({pt['w']}x{pt['h']}): {short}")

            if await try_find_group(page, f"SVG{svg['index']}"):
                await context.close()
                return

            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        # 方法D: ビュータブの右クリック（コンテキストメニュー）
        print("\n=== ビュータブの右クリック ===")
        if tab_box:
            await gallery_tab.click(button="right")
            await asyncio.sleep(1.5)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_rightclick.png")

            # 右クリックメニューの内容
            rc_texts = await page.evaluate("""() => {
                const menus = document.querySelectorAll(
                    '[role="menu"], [role="menuitem"], [role="dialog"]'
                );
                return Array.from(menus).map(m => m.textContent?.substring(0, 200) || '');
            }""")
            for t in rc_texts:
                print(f"  右クリックメニュー: {t[:80]}")

            if await try_find_group(page, "右クリック"):
                await context.close()
                return

            # 「ビューの編集」系のメニュー項目を探す
            edit_view = page.locator('text=/ビューの編集|Edit view|ビューを編集|View options/')
            if await edit_view.count() > 0:
                await edit_view.first.click()
                await asyncio.sleep(1)
                if await try_find_group(page, "ビュー編集"):
                    await context.close()
                    return

            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        # 方法E: ビュー設定パネルを直接開くキーボードショートカット
        # 3点ドット（⋯）が見つからない場合、ページ内の全ボタンを列挙
        print("\n=== 全ページボタン一覧 ===")
        all_buttons = await page.evaluate("""() => {
            const btns = document.querySelectorAll(
                'div[role="button"], button, [tabindex="0"]'
            );
            return Array.from(btns).map(b => {
                const rect = b.getBoundingClientRect();
                return {
                    tag: b.tagName,
                    text: b.textContent?.trim()?.substring(0, 50) || '',
                    ariaLabel: b.getAttribute('aria-label') || '',
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height)
                };
            }).filter(b => b.w > 0 && b.y > 0 && b.y < 200);
        }""")

        print(f"  上部のボタン数: {len(all_buttons)}")
        for btn in all_buttons:
            print(f"    {btn['tag']} text='{btn['text'][:30]}' aria='{btn['ariaLabel']}' "
                  f"pos=({btn['x']},{btn['y']}) size={btn['w']}x{btn['h']}")

        # 最終フォールバック
        await page.screenshot(path=f"{SCREENSHOT_DIR}/pw_final.png")
        print("\n自動設定に失敗しました。スクリーンショットを確認してください。")
        print("10秒後にブラウザを閉じます...")
        await asyncio.sleep(10)
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
