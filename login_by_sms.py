import asyncio
import json
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    phone = os.environ.get('KUAISHOU_PHONE', '')
    code = os.environ.get('KUAISHOU_CODE', '')
    
    if not phone:
        print('ERROR: Please set KUAISHOU_PHONE environment variable', flush=True)
        sys.exit(1)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN'
        )
        page = await context.new_page()
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        # Go to login page
        await page.goto('https://passport.kuaishou.com/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Click "验证码登录"
        await page.evaluate('''() => {
            const spans = document.querySelectorAll("span");
            for (const span of spans) {
                if (span.innerText.trim() === '验证码登录') {
                    span.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }''')
        await page.wait_for_timeout(2000)
        
        # Input phone number
        await page.fill('input[placeholder="请输入手机号"]', phone)
        await page.wait_for_timeout(500)
        
        # Click "获取验证码"
        await page.evaluate('''() => {
            const buttons = document.querySelectorAll("button, span, div");
            for (const btn of buttons) {
                if (btn.innerText.trim() === '获取验证码') {
                    btn.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }''')
        await page.wait_for_timeout(2000)
        await page.screenshot(path='验证码已发送.png')
        print('VERIFICATION_CODE_SENT', flush=True)
        
        # Wait for code if not provided
        if not code:
            print('WAITING_FOR_CODE', flush=True)
            # Need to wait for user to provide code via environment variable update
            # This is a workaround - we'll check a file for the code
            code_file = Path('/workspace/verification_code.txt')
            for i in range(100):
                await page.wait_for_timeout(3000)
                if code_file.exists():
                    code = code_file.read_text().strip()
                    if code:
                        print('CODE_RECEIVED', flush=True)
                        break
                try:
                    body = await page.inner_text('body')
                    if '验证码已失效' in body:
                        print('CODE_EXPIRED', flush=True)
                        break
                except:
                    pass
        
        if not code:
            print('NO_CODE_PROVIDED', flush=True)
            await browser.close()
            sys.exit(1)
        
        # Input code
        await page.fill('input[placeholder="请输入验证码"]', code)
        await page.wait_for_timeout(500)
        
        # Click login button
        await page.evaluate('''() => {
            const buttons = document.querySelectorAll("button");
            for (const btn of buttons) {
                if (btn.innerText.trim() === '登录') {
                    btn.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }''')
        await page.wait_for_timeout(5000)
        await page.screenshot(path='login_result.png')
        
        # Check login result
        url = page.url
        body = await page.inner_text('body')
        
        if 'passport' in url and 'login' in url:
            if '验证码错误' in body or '验证码已失效' in body:
                print('LOGIN_FAILED_INVALID_CODE', flush=True)
            else:
                print('LOGIN_FAILED', flush=True)
            await browser.close()
            return
        
        print('LOGIN_SUCCESS', flush=True)
        
        # Save session
        state = await context.storage_state()
        Path('/workspace/kuaishou_session.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))
        
        # Navigate to target
        print('NAVIGATING_TO_TARGET', flush=True)
        await page.goto('https://v.kuaishou.com/J5fMwYm2', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path='target.png')
        
        # Try to click 私信
        result = await page.evaluate('''() => {
            const all = document.querySelectorAll("button, a, [role='button']");
            for (const el of all) {
                const t = (el.innerText || '').trim();
                if (t === '私信' || t === '发消息') { el.click(); return 'clicked: ' + t; }
            }
            return 'not found';
        }''')
        print(f'CLICK_MSG: {result}', flush=True)
        await page.wait_for_timeout(3000)
        await page.screenshot(path='chat.png')
        
        # Type and send
        await page.evaluate('''() => {
            const inputs = document.querySelectorAll("textarea, div[contenteditable], input[type='text']");
            for (const inp of inputs) {
                const rect = inp.getBoundingClientRect();
                if (rect.width > 0) {
                    if (inp.tagName === 'DIV') {
                        inp.innerText = "u";
                        inp.dispatchEvent(new Event("input", {bubbles: true}));
                    } else {
                        inp.value = "u";
                    }
                    return 'typed';
                }
            }
            return 'no input';
        }''')
        await page.wait_for_timeout(500)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(3000)
        await page.screenshot(path='sent.png')
        print('DONE', flush=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
