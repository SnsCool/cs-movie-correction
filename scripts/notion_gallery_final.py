"""
Browser Use + Custom Controller Actions でNotionギャラリービュー設定。
Browser Use の Page/Element API (CDP) を使用。
textContent は element.evaluate("() => this.textContent") で取得。
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, BrowserProfile, BrowserSession, Controller
from browser_use.llm.google.chat import ChatGoogle
from pydantic import BaseModel

NOTION_URL = "https://www.notion.so/301f3b0fba85801ebbbae30bda6ee7aa"
CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)

controller = Controller()


class EmptyParam(BaseModel):
    pass


async def find_and_click_by_text(page, css_selector, text, timeout=5):
    """CSS selector で要素一覧を取得し、textContent に text を含む要素をクリック。"""
    for attempt in range(timeout):
        elements = await page.get_elements_by_css_selector(css_selector)
        print(f"  [{css_selector}] 要素数: {len(elements)} (attempt {attempt+1})")
        for el in elements:
            try:
                inner = await el.evaluate("() => this.textContent")
                if inner and text in inner:
                    print(f"  → Found '{text}' in '{inner.strip()[:40]}', clicking...")
                    await el.click()
                    return True
            except Exception as e:
                print(f"  → evaluate error: {e}")
                continue
        await asyncio.sleep(1)
    return False


async def click_by_js(page, js_code):
    """page.evaluate で JS コードを実行してクリック。"""
    result = await page.evaluate(js_code)
    print(f"  → JS result: {result}")
    return result


@controller.action(
    "Set gallery layout on the Notion database view. "
    "Opens settings > layout > clicks gallery button.",
    param_model=EmptyParam,
)
async def set_gallery_layout(params: EmptyParam, browser_session: BrowserSession):
    page = await browser_session.get_current_page()
    if not page:
        return "ERROR: page is None"

    print("\n=== set_gallery_layout START ===")

    # 1. Click 設定 button via JS (most reliable)
    print("1. 設定ボタンをクリック...")
    r = await click_by_js(
        page,
        """() => {
        var btn = document.querySelector('[aria-label="設定"]')
            || document.querySelector('[aria-label="View settings"]');
        if (btn) { btn.click(); return 'CLICKED'; }
        return 'NOT_FOUND';
    }""",
    )
    if "NOT_FOUND" in str(r):
        return "ERROR: 設定ボタンが見つかりません"
    await asyncio.sleep(2)

    # 2. Click レイアウト menuitem via JS
    print("2. レイアウトをクリック...")
    r = await click_by_js(
        page,
        """() => {
        var items = document.querySelectorAll('[role="menuitem"]');
        for (var i = 0; i < items.length; i++) {
            var t = items[i].textContent;
            if (t && (t.indexOf('レイアウト') >= 0 || t.indexOf('Layout') >= 0)) {
                items[i].click();
                return 'CLICKED:' + t.trim().substring(0, 30);
            }
        }
        var texts = [];
        items.forEach(function(m) { texts.push(m.textContent.trim().substring(0, 30)); });
        return 'NOT_FOUND menuitems=[' + texts.join(', ') + ']';
    }""",
    )
    if "NOT_FOUND" in str(r):
        return f"ERROR: レイアウトが見つかりません ({r})"
    await asyncio.sleep(2)

    # 3. Click ギャラリー - use CDP Element.click (real mouse event, not JS)
    print("3. ギャラリーをクリック...")
    ok = await find_and_click_by_text(page, '[role="button"]', "ギャラリー")
    if not ok:
        ok = await find_and_click_by_text(page, "div", "ギャラリー")
    if not ok:
        # Fallback: try JS click
        r = await click_by_js(
            page,
            """() => {
            var btns = document.querySelectorAll('[role="button"]');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim() === 'ギャラリー') {
                    btns[i].click();
                    return 'JS_CLICKED';
                }
            }
            var divs = document.querySelectorAll('div');
            for (var j = 0; j < divs.length; j++) {
                if (divs[j].textContent.trim() === 'ギャラリー' && divs[j].offsetParent !== null) {
                    divs[j].click();
                    return 'JS_DIV_CLICKED';
                }
            }
            return 'NOT_FOUND';
        }""",
        )
        if "NOT_FOUND" in str(r):
            return "ERROR: ギャラリーが見つかりません"
    await asyncio.sleep(3)

    # 4. Close panel
    print("4. パネルを閉じる...")
    await click_by_js(
        page,
        """() => {
        var close = document.querySelector('[aria-label="閉じる"]')
            || document.querySelector('[aria-label="Close"]');
        if (close) { close.click(); return 'CLOSED'; }
        return 'NO_CLOSE_BTN';
    }""",
    )
    await asyncio.sleep(1)

    # Check result
    result = await page.evaluate(
        "() => JSON.stringify({gallery: !!document.querySelector('.notion-gallery-view'), table: !!document.querySelector('.notion-table-view')})"
    )
    print(f"=== set_gallery_layout END: {result} ===\n")
    return f"Gallery layout done. Result: {result}"


@controller.action(
    "Set tag grouping on the Notion database view. "
    "Opens settings > group > selects tag property.",
    param_model=EmptyParam,
)
async def set_tag_grouping(params: EmptyParam, browser_session: BrowserSession):
    page = await browser_session.get_current_page()
    if not page:
        return "ERROR: page is None"

    print("\n=== set_tag_grouping START ===")

    # 1. Click 設定 button via JS
    print("1. 設定ボタンをクリック...")
    r = await click_by_js(
        page,
        """() => {
        var btn = document.querySelector('[aria-label="設定"]')
            || document.querySelector('[aria-label="View settings"]');
        if (btn) { btn.click(); return 'CLICKED'; }
        return 'NOT_FOUND';
    }""",
    )
    if "NOT_FOUND" in str(r):
        return "ERROR: 設定ボタンが見つかりません"
    await asyncio.sleep(2)

    # 2. Click グループ menuitem via JS
    print("2. グループをクリック...")
    r = await click_by_js(
        page,
        """() => {
        var items = document.querySelectorAll('[role="menuitem"]');
        for (var i = 0; i < items.length; i++) {
            var t = items[i].textContent;
            if (t && (t.indexOf('グループ') >= 0 || t === 'Group')) {
                items[i].click();
                return 'CLICKED:' + t.trim().substring(0, 30);
            }
        }
        return 'NOT_FOUND';
    }""",
    )
    if "NOT_FOUND" in str(r):
        return "ERROR: グループが見つかりません"
    await asyncio.sleep(2)

    # 3. Click タグ option via CDP Element.click
    print("3. タグを選択...")
    ok = await find_and_click_by_text(page, '[role="option"]', "タグ")
    if not ok:
        # JS fallback
        r = await click_by_js(
            page,
            """() => {
            var opts = document.querySelectorAll('[role="option"]');
            for (var i = 0; i < opts.length; i++) {
                if (opts[i].textContent.indexOf('タグ') >= 0 || opts[i].textContent === 'Tags') {
                    opts[i].click();
                    return 'CLICKED:' + opts[i].textContent.trim();
                }
            }
            var texts = [];
            opts.forEach(function(o) { texts.push(o.textContent.trim().substring(0, 30)); });
            return 'NOT_FOUND opts=[' + texts.join(', ') + ']';
        }""",
        )
        if "NOT_FOUND" in str(r):
            return f"ERROR: タグが見つかりません ({r})"
    await asyncio.sleep(2)

    # 4. Close panel
    print("4. パネルを閉じる...")
    await click_by_js(
        page,
        """() => {
        var close = document.querySelector('[aria-label="閉じる"]')
            || document.querySelector('[aria-label="Close"]');
        if (close) { close.click(); return 'CLOSED'; }
        return 'NO_CLOSE_BTN';
    }""",
    )
    await asyncio.sleep(1)

    print("=== set_tag_grouping END ===\n")
    return "Tag grouping set successfully"


async def main():
    profile = BrowserProfile(
        user_data_dir=CHROME_USER_DATA_DIR,
        headless=False,
        window_size={"width": 1400, "height": 900},
    )

    llm = ChatGoogle(
        model="gemini-2.0-flash",
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    agent = Agent(
        task=f"""
Navigate to {NOTION_URL} and wait for the page to fully load (about 5 seconds).
The page is called 講義動画 and contains a database view called 動画一覧.

Once the page is loaded, perform these 2 actions in order:
1. Call set_gallery_layout to change the database view to gallery layout
2. Call set_tag_grouping to group the database by tags

IMPORTANT: ONLY use the custom actions. Do NOT click any DOM elements directly.
After both actions complete, report the results.
""",
        llm=llm,
        browser_session=BrowserSession(browser_profile=profile),
        controller=controller,
        max_actions_per_step=2,
    )

    print("Starting Browser Use agent...")
    result = await agent.run(max_steps=15)
    print(f"\nAgent final result: {result}")

    await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
