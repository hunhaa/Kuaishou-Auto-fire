#!/usr/bin/env python3
"""快手自动续火花 - 功能测试脚本"""
import asyncio
import sys
from playwright.async_api import async_playwright

async def test_search():
    """测试搜索功能"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        print("=" * 50)
        print("测试1: 页面加载")
        await page.goto('https://www.kuaishou.com/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        title = await page.title()
        assert '快手' in title or '精彩' in title, f"标题异常: {title}"
        print(f"  ✅ 页面加载成功 (标题: {title})")

        print("\n测试2: 搜索框定位")
        search_selectors = [
            "input[placeholder*='搜索']",
            "input[placeholder*='search']",
            "input[type='search']",
        ]
        search_input = None
        for sel in search_selectors:
            search_input = await page.query_selector(sel)
            if search_input:
                print(f"  ✅ 找到搜索框 (选择器: {sel})")
                break
        if not search_input:
            print("  ❌ 未找到搜索框")
            return False

        print("\n测试3: 输入搜索关键词")
        await search_input.click()
        await page.wait_for_timeout(300)
        await search_input.fill("")
        await page.wait_for_timeout(200)
        test_keyword = "测试"
        await search_input.fill(test_keyword)
        await page.wait_for_timeout(3000)
        print(f"  ✅ 已输入搜索关键词: {test_keyword}")

        print("\n测试4: 检查搜索结果")
        user_selectors = [
            "a[href*='profile']",
            "a[href*='/user/']",
            "a[href*='user_id']",
        ]
        found = False
        for sel in user_selectors:
            el = await page.query_selector(sel)
            if el:
                href = await el.get_attribute("href")
                print(f"  ✅ 找到用户链接: {href}")
                found = True
                break
        if not found:
            body_text = await page.inner_text("body")
            has_results = len(body_text) > 1000
            print(f"  ⚠️ 未找到profile链接，但页面内容长度: {len(body_text)}")

        print("\n测试5: 登录状态检测")
        body_text = await page.inner_text("body")
        if "立即登录" in body_text or "登录即可" in body_text:
            print("  ✅ 正确检测到未登录状态")
        else:
            print("  ℹ️ 页面可能已登录或状态不同")

        print("\n" + "=" * 50)
        print("所有核心功能测试完成！")
        print("=" * 50)

        await browser.close()
        return True

if __name__ == "__main__":
    asyncio.run(test_search())