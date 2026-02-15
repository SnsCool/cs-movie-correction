"""
Browser Use でDiscordチャンネルからメッセージを抽出。
Chrome プロファイルでログイン済みの状態を利用。
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, BrowserProfile, BrowserSession, Controller
from browser_use.llm.google.chat import ChatGoogle
from pydantic import BaseModel

CHROME_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
)

CHANNELS = [
    {
        "name": "1on1アーカイブ",
        "url": "https://discord.com/channels/1398982066682593420/1416428648482996337",
    },
    {
        "name": "マネタイズ動画講義",
        "url": "https://discord.com/channels/1398982066682593420/1411044183032201439",
    },
    {
        "name": "グルコンアーカイブ",
        "url": "https://discord.com/channels/1398982066682593420/1425869859685924968",
    },
]

controller = Controller()


class ExtractParam(BaseModel):
    pass


class ScrollParam(BaseModel):
    direction: str = "up"


@controller.action(
    "Scroll the Discord message list up to load older messages.",
    param_model=ScrollParam,
)
async def scroll_messages(params: ScrollParam, browser_session: BrowserSession):
    page = await browser_session.get_current_page()
    if not page:
        return "ERROR: page is None"

    direction = -3000 if params.direction == "up" else 3000
    result = await page.evaluate(
        f"""() => {{
        var scroller = document.querySelector('[class*="scroller_"][data-list-id="chat-messages"]')
            || document.querySelector('[class*="scrollerInner"]')?.parentElement
            || document.querySelector('main [class*="scroller"]');
        if (scroller) {{
            var before = scroller.scrollTop;
            scroller.scrollBy(0, {direction});
            return 'scrolled from ' + before + ' to ' + scroller.scrollTop;
        }}
        return 'NO_SCROLLER';
    }}"""
    )
    await asyncio.sleep(2)
    return f"Scroll result: {result}"


@controller.action(
    "Extract all visible messages from the current Discord channel. "
    "Returns JSON array with date, author, content, and links.",
    param_model=ExtractParam,
)
async def extract_messages(params: ExtractParam, browser_session: BrowserSession):
    page = await browser_session.get_current_page()
    if not page:
        return "ERROR: page is None"

    result = await page.evaluate(
        """() => {
        var messages = [];
        // Discord message list items
        var msgEls = document.querySelectorAll('[id^="chat-messages-"]');
        msgEls.forEach(function(el) {
            var dateHeader = '';
            // Check for date divider above
            var prev = el.previousElementSibling;
            while (prev) {
                if (prev.querySelector('[class*="divider"]') || prev.id.includes('divider')) {
                    var spanText = prev.textContent.trim();
                    if (spanText) dateHeader = spanText;
                    break;
                }
                prev = prev.previousElementSibling;
            }

            // Author and timestamp
            var authorEl = el.querySelector('[class*="username"]');
            var author = authorEl ? authorEl.textContent.trim() : '';

            var timeEl = el.querySelector('time');
            var timestamp = timeEl ? timeEl.getAttribute('datetime') : '';
            var timeText = timeEl ? timeEl.textContent.trim() : '';

            // Message content
            var contentEl = el.querySelector('[id^="message-content-"]');
            var content = contentEl ? contentEl.textContent.trim() : '';

            // Links (YouTube, etc.)
            var links = [];
            var anchors = el.querySelectorAll('a[href]');
            anchors.forEach(function(a) {
                var href = a.href;
                if (href && !href.includes('discord.com') && !href.startsWith('javascript:')) {
                    links.push(href);
                }
            });

            // Embeds (YouTube embeds, etc.)
            var embedEls = el.querySelectorAll('[class*="embed"]');
            var embedTexts = [];
            embedEls.forEach(function(emb) {
                var title = emb.querySelector('[class*="embedTitle"], [class*="embedAuthor"]');
                if (title) embedTexts.push(title.textContent.trim());
            });

            if (content || links.length > 0 || embedTexts.length > 0) {
                messages.push({
                    author: author,
                    timestamp: timestamp,
                    timeText: timeText,
                    content: content.substring(0, 500),
                    links: links,
                    embedTitles: embedTexts
                });
            }
        });
        return JSON.stringify(messages);
    }"""
    )
    return result


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

    all_data = {}

    for ch in CHANNELS:
        print(f"\n{'='*60}")
        print(f"Channel: {ch['name']} - {ch['url']}")
        print(f"{'='*60}")

        session = BrowserSession(browser_profile=profile)

        agent = Agent(
            task=f"""
Navigate to {ch['url']} (Discord channel: {ch['name']}).
Wait for the page to fully load (about 5 seconds).

Once the channel messages are visible, do the following:
1. First, call scroll_messages with direction="up" to load older messages (repeat 3-5 times with short waits)
2. Then call extract_messages to get all visible messages
3. Report the extracted data

IMPORTANT:
- ONLY use scroll_messages and extract_messages actions
- Do NOT click any DOM elements
- After extracting, call done with the extracted JSON data
""",
            llm=llm,
            browser_session=session,
            controller=controller,
            max_actions_per_step=2,
        )

        result = await agent.run(max_steps=15)

        # Extract the final result text
        for r in reversed(result.all_results):
            if r.extracted_content and r.extracted_content.startswith("["):
                try:
                    msgs = json.loads(r.extracted_content)
                    all_data[ch["name"]] = msgs
                    print(f"  → Extracted {len(msgs)} messages")
                except json.JSONDecodeError:
                    pass
                break
            elif r.extracted_content and "extract" not in r.extracted_content.lower():
                all_data[ch["name"]] = r.extracted_content
                print(f"  → Raw data: {r.extracted_content[:200]}")

        await asyncio.sleep(2)

    # Save results
    output_path = Path("assets/discord_messages.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved to {output_path}")

    # Print summary
    for ch_name, msgs in all_data.items():
        print(f"\n{ch_name}:")
        if isinstance(msgs, list):
            for m in msgs:
                print(
                    f"  {m.get('timestamp', '?')[:10]} | {m.get('author', '?')} | {m.get('content', '')[:60]}"
                )
        else:
            print(f"  {str(msgs)[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
