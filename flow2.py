#!/usr/bin/env python3
"""快手扫码登录 + 发送消息 - 精确版"""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
from PIL import Image

SESSION_FILE = Path("kuaishou_session.json")
TARGET_URL = "https://v.kuaishou.com/J5fMwYm2"
MESSAGE = "u"
QR_SCREENSHOT = Path("kuaishou_qr_show.png")

async def capture_qr():
    """Capture QR code and return the page + context for reuse"""
    p = await async_playwright().start()
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
    
    print("打开快手首页...", flush=True)
    await page.goto("https://www.kuaishou.com/new-reco", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(5000)
    
    print("点击登录...", flush=True)
    await page.evaluate("""() => {
        const spans = document.querySelectorAll('span');
        for (const s of spans) {
            if (s.innerText.trim() === '立即') { s.click(); break; }
        }
    }""")
    await page.wait_for_timeout(2000)
    
    # Take full screenshot
    await page.screenshot(path="kuaishou_full_new.png")
    
    # Crop QR code with precise coordinates
    img = Image.open("kuaishou_full_new.png")
    # QR code in popup: approximately x:580-715, y:370-505
    qr = img.crop((570, 360, 725, 515))
    qr = qr.resize((500, 500), Image.LANCZOS)
    qr.save(str(QR_SCREENSHOT))
    print(f"二维码已保存: {QR_SCREENSHOT.absolute()}", flush=True)
    
    return p, browser, context, page

async def wait_for_login(page, max_wait=180):
    """Wait for user to scan QR code and login"""
    print(f"\n等待扫码登录中... (最多{max_wait}秒)", flush=True)
    for i in range(max_wait // 3):
        await page.wait_for_timeout(3000)
        try:
            body = await page.inner_text("body")
            if "立即登录" not in body and "登录即可享受" not in body:
                if any(k in body for k in ["我的主页", "我的作品", "退出登录"]):
                    print(f"✅ 登录成功！({(i+1)*3}秒)", flush=True)
                    return True
        except Exception:
            pass
        if i % 5 == 0 and i > 0:
            print(f"  等待中... ({(i+1)*3}s)", flush=True)
    return False

async def send_message(page):
    """Navigate to target URL and send message"""
    print(f"\n打开目标页面: {TARGET_URL}", flush=True)
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
    print(f"实际URL: {page.url}", flush=True)
    await page.wait_for_timeout(3000)
    await page.screenshot(path="kuaishou_target_new.png")
    
    # Find message button
    print("查找发消息按钮...", flush=True)
    msg_btn = None
    for sel in ["button:has-text('发消息')", "button:has-text('私信')",
                 "a:has-text('发消息')", "a:has-text('私信')",
                 "[class*='user-action'] button", "[class*='action'] a"]:
        msg_btn = await page.query_selector(sel)
        if msg_btn:
            print(f"  ✅ 找到: {sel}", flush=True)
            break
    
    if not msg_btn:
        print("  ❌ 未找到发消息按钮", flush=True)
        body = await page.inner_text("body")
        print(f"  页面内容: {body[:500]}", flush=True)
        return False
    
    print("点击发消息...", flush=True)
    await msg_btn.click()
    await page.wait_for_timeout(2000)
    await page.screenshot(path="kuaishou_chat_new.png")
    
    # Find input box
    print("查找输入框...", flush=True)
    textarea = None
    for sel in ["textarea", "div[contenteditable='true']",
                 "input[placeholder*='输入']", "input[placeholder*='消息']",
                 "[class*='chatInput']", "[class*='editor']", "[class*='Input']"]:
        textarea = await page.query_selector(sel)
        if textarea:
            tag = await textarea.evaluate("el => el.tagName")
            print(f"  ✅ 输入框: {sel} ({tag})", flush=True)
            break
    
    if not textarea:
        print("  ❌ 未找到输入框", flush=True)
        return False
    
    print(f"发送消息: '{MESSAGE}'", flush=True)
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
    await page.screenshot(path="kuaishou_sent_new.png")
    print(f"✅🎉 消息已发送！", flush=True)
    return True

async def main():
    p, browser, context, page = await capture_qr()
    
    print("\n" + "=" * 50, flush=True)
    print("📲 请用快手APP扫描截图中的二维码", flush=True)
    print(f"   文件: {QR_SCREENSHOT.absolute()}", flush=True)
    print("=" * 50 + "\n", flush=True)
    
    logged_in = await wait_for_login(page, max_wait=180)
    
    if not logged_in:
        print("❌ 登录超时", flush=True)
        await browser.close()
        await p.stop()
        return
    
    # Save session
    state = await context.storage_state()
    SESSION_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print("会话已保存", flush=True)
    
    success = await send_message(page)
    
    await browser.close()
    await p.stop()
    
    if success:
        print("\n✅ 完成！", flush=True)
    else:
        print("\n❌ 发送失败", flush=True)

if __name__ == "__main__":
    asyncio.run(main())