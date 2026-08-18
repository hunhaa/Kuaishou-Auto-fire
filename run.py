#!/usr/bin/env python3
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
from PIL import Image

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
        img = Image.open("qr.png")
        qr = img.crop((575, 365, 720, 510))
        qr = qr.resize((500, 500), Image.LANCZOS)
        qr.save("qr.png")

        print("qr.png generated, waiting for login...", flush=True)

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

        await page.goto("https://v.kuaishou.com/J5fMwYm2", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="target.png")

        for sel in ["button:has-text('发消息')", "button:has-text('私信')", "a:has-text('发消息')", "a:has-text('私信')"]:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                break
        await page.wait_for_timeout(2000)

        for sel in ["textarea", "div[contenteditable='true']", "input[placeholder*='输入']", "[class*='chatInput']"]:
            ta = await page.query_selector(sel)
            if ta:
                tag = await ta.evaluate("el => el.tagName")
                await ta.click()
                await page.wait_for_timeout(300)
                if tag == "DIV":
                    await ta.evaluate("el => el.innerText = 'u'")
                    await ta.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true}))")
                else:
                    await ta.fill("u")
                await page.wait_for_timeout(500)
                send = await page.query_selector("button:has-text('发送'), button[class*='send']")
                if send:
                    await send.click()
                else:
                    await page.keyboard.press("Enter")
                break

        await page.wait_for_timeout(2000)
        await page.screenshot(path="sent.png")
        print("DONE", flush=True)
        await browser.close()

asyncio.run(main())
