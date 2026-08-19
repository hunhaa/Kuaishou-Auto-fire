#!/usr/bin/env python3
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

        await page.goto("https://www.kuaishou.com/new-reco", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)

        await page.evaluate("""() => {
            const spans = document.querySelectorAll('span');
            for (const s of spans) { if (s.innerText.trim() === '立即') { s.click(); break; } }
        }""")
        await page.wait_for_timeout(2000)

        await page.screenshot(path="qr.png")
        print("qr.png generated", flush=True)

        for i in range(60):
            await page.wait_for_timeout(3000)
            try:
                body = await page.inner_text("body")
                if "立即登录" not in body and "登录即可享受" not in body:
                    if any(k in body for k in ["我的主页", "我的作品", "退出登录"]):
                        print(f"LOGGED_IN after {(i+1)*3}s", flush=True)
                        break
            except:
                pass

        state = await context.storage_state()
        Path("session.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))

        print("Opening target page...", flush=True)
        await page.goto("https://v.kuaishou.com/J5fMwYm2", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        await page.screenshot(path="target.png")
        print("target.png saved", flush=True)

        body = await page.inner_text("body")
        if "security verification" in body.lower() or "Please complete" in body:
            print("Security check found, waiting 15s...", flush=True)
            await page.wait_for_timeout(15000)
            await page.screenshot(path="target.png")

        print("Clicking message button via JS...", flush=True)
        await page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role="button"], div[class*="btn"]');
            for (const el of all) {
                const text = (el.innerText || '').trim();
                if (text === '私信' || text === '发消息') {
                    el.click();
                    return 'clicked: ' + text;
                }
            }
            for (const el of all) {
                const text = (el.innerText || '').trim();
                if (text.includes('消息') || text.includes('私信')) {
                    el.click();
                    return 'clicked partial: ' + text;
                }
            }
            return 'not found';
        }""")

        await page.wait_for_timeout(3000)
        await page.screenshot(path="chat.png")
        print("chat.png saved", flush=True)

        print("Typing message...", flush=True)
        await page.evaluate("""() => {
            const inputs = document.querySelectorAll('textarea, div[contenteditable="true"], input[type="text"], input[placeholder*="输入"], input[placeholder*="消息"]');
            for (const inp of inputs) {
                const rect = inp.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    if (inp.tagName === 'DIV') {
                        inp.innerText = 'u';
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                    } else {
                        inp.value = 'u';
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                    return 'typed in: ' + inp.tagName;
                }
            }
            return 'no input found';
        }""")

        await page.wait_for_timeout(500)

        print("Sending...", flush=True)
        await page.evaluate("""() => {
            const sends = document.querySelectorAll('button');
            for (const btn of sends) {
                if (btn.innerText.trim() === '发送') {
                    btn.click();
                    return 'sent via button';
                }
            }
            return 'trying enter';
        }""")

        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        await page.screenshot(path="sent.png")
        print("DONE", flush=True)
        await browser.close()

asyncio.run(main())
