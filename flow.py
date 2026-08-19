#!/usr/bin/env python3
"""快手扫码登录 + 发送消息 完整流程"""
import asyncio, json, sys, os
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_FILE = Path("kuaishou_session.json")
QR_FILE = Path("kuaishou_qr_final.png")
TARGET_URL = "https://v.kuaishou.com/J5fMwYm2"
MESSAGE = "u"

async def main():
    log = lambda msg: print(msg, flush=True)
    
    log("1️⃣ 启动浏览器...")
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
        
        log("2️⃣ 打开快手首页...")
        await page.goto("https://www.kuaishou.com/new-reco", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        
        log("3️⃣ 点击登录按钮...")
        btn = await page.query_selector("span.text-sub")
        if not btn:
            btn = await page.query_selector(".btn-wrapper")
        if btn:
            await btn.click()
            await page.wait_for_timeout(2000)
        else:
            log("   未找到登录按钮，尝试JS点击...")
            await page.evaluate("""() => {
                const spans = document.querySelectorAll('span');
                for (const s of spans) {
                    if (s.innerText.trim() === '立即') { s.click(); break; }
                }
            }""")
            await page.wait_for_timeout(2000)
        
        log("4️⃣ 截取二维码...")
        await page.screenshot(path="kuaishou_full.png")
        
        # Crop QR code
        try:
            from PIL import Image
            img = Image.open("kuaishou_full.png")
            qr = img.crop((575, 355, 720, 505))
            qr = qr.resize((400, 400), Image.LANCZOS)
            qr.save(str(QR_FILE))
            log(f"   ✅ 二维码已保存: {QR_FILE.absolute()}")
        except Exception as e:
            log(f"   截图裁剪失败: {e}")
        
        log("")
        log("=" * 50)
        log("📲 请用快手APP扫描二维码登录")
        log(f"   截图文件: {QR_FILE.absolute()}")
        log("   扫码后在手机上点击「确认登录」")
        log("   等待时间: 最多180秒")
        log("=" * 50)
        log("")
        
        log("5️⃣ 等待扫码登录...")
        logged_in = False
        for i in range(60):
            await page.wait_for_timeout(3000)
            try:
                body = await page.inner_text("body")
                if "立即登录" not in body and "登录即可享受" not in body:
                    if any(k in body for k in ["我的主页", "我的作品", "退出登录", "粉丝"]):
                        logged_in = True
                        log(f"   ✅ 登录成功！({(i+1)*3}秒)")
                        break
            except Exception:
                pass
            if i % 5 == 0:
                log(f"   等待中... ({(i+1)*3}s)")
        
        if not logged_in:
            log("❌ 登录超时")
            await browser.close()
            return
        
        log("6️⃣ 保存会话...")
        state = await context.storage_state()
        SESSION_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        log("   ✅ 会话已保存")
        
        log(f"7️⃣ 打开目标页面: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        log(f"   实际URL: {page.url}")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="kuaishou_target.png")
        log("   📸 目标页截图: kuaishou_target.png")
        
        log("8️⃣ 查找发消息按钮...")
        msg_btn = None
        for sel in ["button:has-text('发消息')", "button:has-text('私信')",
                     "a:has-text('发消息')", "a:has-text('私信')",
                     "[class*='user-action'] button"]:
            msg_btn = await page.query_selector(sel)
            if msg_btn:
                log(f"   ✅ 找到: {sel}")
                break
        
        if not msg_btn:
            log("   ❌ 未找到发消息按钮")
            body = await page.inner_text("body")
            log(f"   页面内容:\n{body[:500]}")
            await browser.close()
            return
        
        log("9️⃣ 点击发消息...")
        await msg_btn.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path="kuaishou_chat.png")
        log("   📸 聊天页截图: kuaishou_chat.png")
        
        log("🔟 输入消息并发送...")
        textarea = None
        for sel in ["textarea", "div[contenteditable='true']",
                     "input[placeholder*='输入']", "input[placeholder*='消息']",
                     "[class*='chatInput']", "[class*='editor']"]:
            textarea = await page.query_selector(sel)
            if textarea:
                tag = await textarea.evaluate("el => el.tagName")
                log(f"   ✅ 输入框: {sel} ({tag})")
                break
        
        if not textarea:
            log("   ❌ 未找到输入框")
            body = await page.inner_text("body")
            log(f"   内容:\n{body[:500]}")
            await browser.close()
            return
        
        await textarea.click()
        await page.wait_for_timeout(300)
        tag = await textarea.evaluate("el => el.tagName")
        if tag == "DIV":
            await textarea.evaluate(f"el => el.innerText = '{MESSAGE}'")
            await textarea.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true}))")
        else:
            await textarea.fill(MESSAGE)
        await page.wait_for_timeout(500)
        
        send_btn = await page.query_selector("button:has-text('发送'), button[class*='send']")
        if send_btn:
            await send_btn.click()
        else:
            await page.keyboard.press("Enter")
        
        await page.wait_for_timeout(2000)
        await page.screenshot(path="kuaishou_sent.png")
        log("   📸 发送后截图: kuaishou_sent.png")
        
        log("")
        log("=" * 50)
        log(f"  ✅🎉 消息 \"{MESSAGE}\" 已成功发送！")
        log("=" * 50)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())