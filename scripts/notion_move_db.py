"""
Browser Use エージェントを使って動画一覧DBを「講義動画」ページに移動する。
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, BrowserProfile
from browser_use.llm.google.chat import ChatGoogle

# 動画一覧 DB のURL
SOURCE_DB_URL = "https://www.notion.so/301f3b0fba85815aa696d4836fe88bb6"
# 移動先: 講義動画ページ
TARGET_PAGE_TITLE = "講義動画"

CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)


async def main():
    llm = ChatGoogle(
        model="gemini-2.0-flash",
        api_key=os.environ["GEMINI_API_KEY"],
    )

    profile = BrowserProfile(
        user_data_dir=CHROME_USER_DATA_DIR,
        headless=False,
        window_size={"width": 1400, "height": 900},
    )

    task = f"""
以下のNotionデータベース「動画一覧」を「{TARGET_PAGE_TITLE}」ページに移動してください。

手順:
1. {SOURCE_DB_URL} にアクセスする
2. ページ右上の「⋯」（その他のアクション/三点メニュー）をクリックする
3. メニューから「別ページへ移動」をクリックする
4. 検索ボックスに「{TARGET_PAGE_TITLE}」と入力する
5. 表示された「{TARGET_PAGE_TITLE}」を選択してクリックする
6. 移動が完了したことを確認する

重要:
- Notionにログイン済みの状態です
- 「別ページへ移動」は日本語UIで表示されるメニュー項目です
- 移動先の「{TARGET_PAGE_TITLE}」はNotionのページです
"""

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=profile,
        max_actions_per_step=3,
    )

    print("Browser Use エージェント開始（DB移動）...")
    result = await agent.run(max_steps=20)

    print(f"\n結果: {result.is_done()}")
    if result.is_done():
        final = result.final_result()
        print(f"最終結果: {final}")

    for i, step in enumerate(result.history):
        if step.result:
            for r in step.result:
                if r.extracted_content:
                    print(f"  Step {i}: {r.extracted_content[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
