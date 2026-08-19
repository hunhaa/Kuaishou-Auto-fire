#!/usr/bin/env python3
"""快手扫码登录 + 发送消息 - 完整流程脚本"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_FILE = Path("kuaishou_session.json")
QR_SCREENSHOT = Path("kuaishou_qr.png")
TARGET_URL = "https://v.kuaishou.com/J5fMwYm2"
MESSAGE = "u"

async def main():
    async with async_playwright() as p:
        print("🚀 启动浏览器...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        print("📱 打开快手首页...")
        await page.goto("https://www.kuaishou.com/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        print("🔐 打开登录弹窗...")
        login_btn = await page.query_selector(".sidebar-login-b, .btn-wrapper")
        if login_btn:
            await login_btn.click()
            await page.wait_for_timeout(2000)
        else:
            print("未找到登录按钮，尝试其他方式...")
            await page.goto("https://www.kuaishou.com/?login=1", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

        # Save QR code screenshot (crop just the QR area)
        await page.screenshot(path=str(QR_SCREENSHOT))
        print(f"\n📸 登录二维码已保存: {QR_SCREENSHOT.absolute()}")

        # Also crop just the QR code
        try:
            from PIL import Image
            img = Image.open(str(QR_SCREENSHOT))
            qr_crop = img.crop((500, 320, 780, 580))
            qr_crop = qr_crop.resize((500, 500), Image.LANCZOS)
            qr_crop.save(str(QR_SCREENSHOT))
        except Exception:
            pass

        print("\n" + "=" * 60)
        print("📲 请用快手APP扫描下方截图中的二维码登录")
        print(f"   截图文件: {QR_SCREENSHOT.absolute()}")
        print("   扫码后请在手机上确认登录")
        print("   脚本将自动检测登录状态...")
        print("=" * 60)

        # Wait for login
        print("\n⏳ 等待登录中...")
        logged_in = False
        for i in range(60):
            await page.wait_for_timeout(3000)
            try:
                body_text = await page.inner_text("body")
                if "立即登录" not in body_text and "登录即可享受" not in body_text:
                    has_user = any(kw in body_text for kw in ["我的主页", "我的作品", "粉丝", "关注", "退出登录"])
                    if has_user:
                        logged_in = True
                        elapsed = (i + 1) * 3
                        print(f"\n✅ 检测到登录成功！({elapsed}秒)")
                        break
            except Exception:
                pass
            if i % 5 == 0:
                print(f"   等待中... ({(i+1)*3}s)")

        if not logged_in:
            print("\n❌ 登录超时（超过180秒）")
            await browser.close()
            return

        # Save session
        state = await context.storage_state()
        SESSION_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        print("✅ 会话已保存")

        # Navigate to target URL
        print(f"\n🎯 打开目标页面: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        final_url = page.url
        print(f"   实际URL: {final_url}")
        await page.wait_for_timeout(3000)

        # Screenshot target page
        await page.screenshot(path="kuaishou_target_page.png")
        print("📸 目标页面截图: kuaishou_target_page.png")

        # Find and click message button
        print("\n🔍 查找发消息按钮...")
        msg_btn_selectors = [
            "button:has-text('发消息')",
            "button:has-text('私信')",
            "a:has-text('发消息')",
            "a:has-text('私信')",
            "[class*='user-action'] button",
            "[class*='action'] a:has-text('消息')",
        ]

        msg_btn = None
        for sel in msg_btn_selectors:
            msg_btn = await page.query_selector(sel)
            if msg_btn:
                print(f"   ✅ 找到按钮: {sel}")
                break

        if not msg_btn:
            print("   ❌ 未找到发消息按钮")
            body_text = await page.inner_text("body")
            print(f"\n   页面内容预览:\n{body_text[:500]}")
            await browser.close()
            return

        print("   🖱️ 点击发消息按钮...")
        await msg_btn.click()
        await page.wait_for_timeout(2000)

        # Screenshot chat page
        await page.screenshot(path="kuaishou_chat_page.png")
        print("   📸 聊天界面截图: kuaishou_chat_page.png")

        # Find input box
        print("\n📝 查找消息输入框...")
        textarea_selectors = [
            "textarea",
            "div[contenteditable='true']",
            "input[placeholder*='输入']",
            "input[placeholder*='消息']",
            "[class*='chatInput']",
            "[class*='input'] textarea",
            "[class*='editor']",
            "[class*='Input']",
            "[class*='chat'] [contenteditable]",
        ]

        textarea = None
        for sel in textarea_selectors:
            textarea = await page.query_selector(sel)
            if textarea:
                tag = await textarea.evaluate("el => el.tagName")
                print(f"   ✅ 找到输入框: {sel} (元素: {tag})")
                break

        if not textarea:
            print("   ❌ 未找到输入框")
            body_text = await page.inner_text("body")
            print(f"\n   聊天页内容预览:\n{body_text[:500]}")
            await browser.close()
            return

        # Type and send message
        print(f"\n✍️  输入消息: \"{MESSAGE}\"")
        await textarea.click()
        await page.wait_for_timeout(300)
        tag_name = await textarea.evaluate("el => el.tagName")

        if tag_name == "DIV":
            await textarea.evaluate(f"el => el.innerText = '{MESSAGE}'")
            await textarea.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true}))")
        else:
            await textarea.fill(MESSAGE)
        await page.wait_for_timeout(500)

        # Click send or press Enter
        send_btn = await page.query_selector(
            "button:has-text('发送'), button[class*='send'], button[class*='Send']"
        )
        if send_btn:
            print("   🖱️ 点击发送按钮...")
            await send_btn.click()
        else:
            print("   ⌨️ 按Enter键发送...")
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(2000)

        # Final screenshot
        await page.screenshot(path="kuaishou_sent_page.png")
        print("   📸 发送后截图: kuaishou_sent_page.png")

        print(f"\n{'='*60}")
        print(f"  ✅🎉 消息 \"{MESSAGE}\" 已成功发送！")
        print(f"{'='*60}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())