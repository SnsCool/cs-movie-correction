"""
Browser Use エージェントを使ってNotion動画アーカイブDBの
ギャラリービューでタグによるグループ化を設定する。

Chrome の既存ログインセッションを利用。
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, BrowserProfile
from browser_use.llm.google.chat import ChatGoogle

NOTION_DB_URL = "https://www.notion.so/301f3b0fba85815aa696d4836fe88bb6"
CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)


async def main():
    # Gemini LLM
    llm = ChatGoogle(
        model="gemini-2.0-flash",
        api_key=os.environ["GEMINI_API_KEY"],
    )

    # Chrome の既存プロファイルを使用（ログイン済み）
    profile = BrowserProfile(
        user_data_dir=CHROME_USER_DATA_DIR,
        headless=False,
        window_size={"width": 1400, "height": 900},
    )

    task = f"""
以下のNotionデータベースページで、ギャラリービューのグループ化を設定してください。

URL: {NOTION_DB_URL}

手順:
1. URLにアクセスする
2. 「ギャラリービュー」タブをクリックしてギャラリービューに切り替える
3. ギャラリービュータブの上にマウスをホバーすると、タブの右端に小さな「⋯」(三点リーダー)ボタンが表示されるのでクリックする
4. ドロップダウンメニューから「グループ」をクリックする
5. プロパティ一覧から「タグ」を選択する
6. 設定が完了したことを確認する

重要:
- ページがNotionにログイン済みの状態で表示されるはずです
- 「ギャラリービュー」タブは「Default view」の隣にあります
- 右端にある3つのアイコン（フィルタ、並べ替え、検索）ではなく、タブの⋯メニューを使ってください
"""

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=profile,
        max_actions_per_step=3,
    )

    print("Browser Use エージェント開始...")
    result = await agent.run(max_steps=20)

    print(f"\n結果: {result.is_done()}")
    if result.is_done():
        final = result.final_result()
        print(f"最終結果: {final}")
    else:
        print("タスク未完了")

    # History
    for i, step in enumerate(result.history):
        if step.result:
            for r in step.result:
                if r.extracted_content:
                    print(f"  Step {i}: {r.extracted_content[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
