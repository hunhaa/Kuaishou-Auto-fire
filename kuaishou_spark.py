#!/usr/bin/env python3
"""
快手自动续火花脚本 v2.0
==========================
通过快手网页版自动向指定好友发送私信，维持火花关系。

支持:
  - 定时自动发送 (基于APScheduler)
  - 手动立即发送
  - 多联系人批量发送
  - 会话持久化 (登录一次，长期使用)
  - 浏览器无头/有头模式切换

使用方法:
  1. 编辑 config.yaml 配置好友昵称和消息
  2. python kuaishou_spark.py login    # 首次登录（需在浏览器中完成）
  3. python kuaishou_spark.py send     # 立即发送一次
  4. python kuaishou_spark.py run      # 启动定时任务
  5. python kuaishou_spark.py status   # 查看状态

⚠️ 本脚本仅供学习交流，请勿用于商业用途或骚扰他人
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("kuaishou_spark.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("ks_spark")

CONFIG_PATH = Path("config.yaml")
SESSION_PATH = Path("kuaishou_session.json")


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config

    default = {
        "contacts": [
            {"name": "好友昵称", "message": "今天也要开心呀~"}
        ],
        "schedule": {
            "enabled": True,
            "cron": "0 9 * * *",
            "timezone": "Asia/Shanghai",
        },
        "settings": {
            "headless": False,
            "message_delay": 3,
            "max_retry": 3,
            "retry_delay": 5,
            "page_timeout": 30,
        },
    }
    save_config(default)
    return default


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


class KuaishouBot:
    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start_browser(self):
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        headless = self.config["settings"]["headless"]

        kwargs = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        }
        self.browser = await self.playwright.chromium.launch(**kwargs)

        storage_state = None
        if SESSION_PATH.exists():
            try:
                with open(SESSION_PATH, "r") as f:
                    storage_state = json.load(f)
                log.info("检测到已保存的登录会话")
            except Exception:
                pass

        self.context = await self.browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )

        self.page = await self.context.new_page()
        await self.page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

    async def stop_browser(self):
        for obj in [self.context, self.browser]:
            try:
                if obj:
                    await obj.close()
            except Exception:
                pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

    async def _save_session(self):
        try:
            state = self.context.storage_state()
            with open(SESSION_PATH, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            log.info("会话已保存")
        except Exception as e:
            log.error(f"保存会话失败: {e}")

    async def is_logged_in(self) -> bool:
        try:
            body_text = await self.page.inner_text("body")
            login_phrases = ["立即登录", "立即 登录", "登录即可", "登录后"]
            for phrase in login_phrases:
                if phrase in body_text:
                    return False
            title = await self.page.title()
            if "登录" in title:
                return False
            return True
        except Exception:
            return False

    async def login(self) -> bool:
        log.info("启动快手网页版...")
        await self.page.goto(
            "https://www.kuaishou.com/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await self.page.wait_for_timeout(3000)

        if await self.is_logged_in():
            log.info("已登录")
            await self._save_session()
            return True

        log.info("=" * 60)
        log.info("请在浏览器中完成登录")
        log.info("支持: 扫码 / 手机号 / 微信 / QQ")
        log.info("登录成功后会自动检测并保存会话")
        log.info("=" * 60)

        for i in range(120):
            await self.page.wait_for_timeout(3000)
            if await self.is_logged_in():
                log.info("✅ 登录成功!")
                await self._save_session()
                return True
            if i % 10 == 0 and i > 0:
                log.info(f"等待登录... ({i * 3}s)")

        log.error("登录超时（超过360秒）")
        return False

    async def _search_and_open_user(self, user_name: str) -> bool:
        log.info(f"搜索用户: {user_name}")

        try:
            search_selectors = [
                "input[placeholder*='搜索']",
                "input[placeholder*='search']",
                "input[type='search']",
                ".search-box input",
                "header input",
            ]
            search_input = None
            for sel in search_selectors:
                search_input = await self.page.query_selector(sel)
                if search_input:
                    break

            if not search_input:
                log.error("未找到搜索框")
                return False

            await search_input.click()
            await self.page.wait_for_timeout(300)
            await search_input.fill("")
            await self.page.wait_for_timeout(200)
            await search_input.fill(user_name)
            await self.page.wait_for_timeout(3000)

            user_selectors = [
                "a[href*='profile']",
                "a[href*='/user/']",
                "a[href*='user_id']",
                ".search-result a",
                ".user-item a",
                ".result-card a",
                ".user-card a",
                "[class*='searchResult'] a",
            ]
            for sel in user_selectors:
                el = await self.page.query_selector(sel)
                if el:
                    href = await el.get_attribute("href")
                    if href:
                        url = href if href.startswith("http") else f"https://www.kuaishou.com{href}"
                        log.info(f"找到用户，访问: {url}")
                        await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        await self.page.wait_for_timeout(2000)
                        return True

            log.warning("未找到匹配的用户，尝试直接访问用户页...")
            return False

        except Exception as e:
            log.error(f"搜索失败: {e}")
            return False

    async def _find_and_click_message_button(self) -> bool:
        selectors = [
            "button:has-text('发消息')",
            "a:has-text('发消息')",
            "button:has-text('私信')",
            "a:has-text('私信')",
            "[class*='user-action'] button",
            "[class*='action'] button:has-text('消息')",
        ]
        for sel in selectors:
            btn = await self.page.query_selector(sel)
            if btn:
                await btn.click()
                await self.page.wait_for_timeout(1500)
                log.info("已点击发消息按钮")
                return True

        log.error("未找到发消息按钮")
        return False

    async def _type_and_send(self, message: str) -> bool:
        textarea_selectors = [
            "textarea",
            "div[contenteditable='true']",
            "input[placeholder*='输入']",
            "input[placeholder*='消息']",
            "[class*='input']",
        ]

        for sel in textarea_selectors:
            textarea = await self.page.query_selector(sel)
            if textarea:
                try:
                    await textarea.click()
                    await self.page.wait_for_timeout(300)
                    if await textarea.evaluate("el => el.tagName") == "DIV":
                        await textarea.fill(message)
                    else:
                        await textarea.fill(message)
                    await self.page.wait_for_timeout(500)

                    send_btn = await self.page.query_selector(
                        "button:has-text('发送'), button[class*='send']"
                    )
                    if send_btn:
                        await send_btn.click()
                    else:
                        await self.page.keyboard.press("Enter")

                    await self.page.wait_for_timeout(1000)
                    log.info(f"✅ 消息已发送: {message[:50]}")
                    return True
                except Exception as e:
                    log.error(f"输入消息出错: {e}")
                    continue

        log.error("未找到消息输入框")
        return False

    async def send_message(self, user_name: str, message: str, profile_url: str = "") -> bool:
        settings = self.config["settings"]
        max_retry = settings.get("max_retry", 3)

        target_desc = profile_url or user_name
        for attempt in range(1, max_retry + 1):
            log.info(f"[{attempt}/{max_retry}] 尝试发送给 {target_desc}")

            try:
                if not await self.is_logged_in():
                    log.error("未登录，无法发送")
                    return False

                if profile_url:
                    log.info(f"直接访问用户主页: {profile_url}")
                    await self.page.goto(
                        profile_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await self.page.wait_for_timeout(3000)
                else:
                    await self.page.goto(
                        "https://www.kuaishou.com/",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await self.page.wait_for_timeout(2000)

                    if not await self._search_and_open_user(user_name):
                        continue

                if not await self._find_and_click_message_button():
                    continue

                if await self._type_and_send(message):
                    return True

            except Exception as e:
                log.error(f"发送异常: {e}")

            if attempt < max_retry:
                delay = settings.get("retry_delay", 5)
                log.info(f"等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

        log.error(f"发送给 {target_desc} 失败")
        return False

    async def send_all(self) -> dict:
        contacts = self.config.get("contacts", [])
        if not contacts:
            log.warning("未配置联系人")
            return {}

        delay = self.config["settings"].get("message_delay", 3)
        results = {}

        for i, contact in enumerate(contacts):
            name = contact.get("name", "")
            msg = contact.get("message", "")
            profile_url = contact.get("profile_url", "")

            if i > 0:
                log.info(f"等待 {delay}s...")
                await asyncio.sleep(delay)

            label = profile_url or name
            success = await self.send_message(name, msg, profile_url)
            results[label] = "✅" if success else "❌"

        return results


# ============================================================
# 命令处理函数
# ============================================================

async def cmd_login(config):
    bot = KuaishouBot(config)
    try:
        await bot.start_browser()
        if await bot.login():
            log.info("登录完成！现在可以使用 send 或 run 命令了")
        else:
            log.error("登录失败")
    finally:
        await bot.stop_browser()


async def cmd_send(config):
    bot = KuaishouBot(config)
    try:
        await bot.start_browser()

        if not SESSION_PATH.exists():
            log.error("未检测到登录会话，请先执行 login")
            return

        if not await bot.is_logged_in():
            log.warning("会话已过期，需要重新登录...")
            if not await bot.login():
                return

        results = await bot.send_all()
        log.info("发送结果:")
        for name, status in results.items():
            log.info(f"  {status} {name}")

    finally:
        await bot.stop_browser()


async def cmd_run(config):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone=config["schedule"]["timezone"])

    async def scheduled_job():
        log.info("=" * 50)
        log.info("⏰ 定时任务开始执行")
        bot = KuaishouBot(config)
        try:
            await bot.start_browser()
            if not SESSION_PATH.exists() or not await bot.is_logged_in():
                log.info("需要登录...")
                if not await bot.login():
                    return
            results = await bot.send_all()
            for name, status in results.items():
                log.info(f"  {status} {name}")
        except Exception as e:
            log.error(f"任务异常: {e}")
        finally:
            await bot.stop_browser()
        log.info("✅ 定时任务执行完毕")
        log.info("=" * 50)

    parts = config["schedule"]["cron"].split()
    if len(parts) != 5:
        log.error(f"cron格式错误: {config['schedule']['cron']}")
        return

    trigger = CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4],
    )
    scheduler.add_job(scheduled_job, trigger, id="ks_spark", replace_existing=True)
    scheduler.start()

    log.info("=" * 50)
    log.info("✅ 定时任务已启动")
    log.info(f"   执行时间: 每天 {parts[1]}:{parts[0]}")
    log.info(f"   联系人: {len(config.get('contacts', []))} 个")
    log.info("   按 Ctrl+C 停止")
    log.info("=" * 50)

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("定时任务已停止")


async def cmd_status(config):
    print()
    print("=" * 50)
    print("  快手自动续火花 - 状态面板")
    print("=" * 50)

    session_ok = SESSION_PATH.exists()
    print(f"  登录会话: {'✅ 已保存' if session_ok else '❌ 未找到'}")

    contacts = config.get("contacts", [])
    print(f"  联系人数量: {len(contacts)}")
    for c in contacts:
        name = c.get("name", "")
        profile = c.get("profile_url", "")
        msg = c.get("message", "")[:30]
        if profile:
            display = f"[URL] {profile[:50]}"
        else:
            display = name or "未命名"
        print(f"    • {display}: {msg}")

    sched = config.get("schedule", {})
    enabled = sched.get("enabled", True)
    print(f"  定时任务: {'✅ 启用' if enabled else '❌ 禁用'}")
    print(f"  Cron表达式: {sched.get('cron', 'N/A')}")

    settings = config.get("settings", {})
    headless = settings.get("headless", False)
    print(f"  浏览器模式: {'无头' if headless else '有头(可见)'}")
    print(f"  消息间隔: {settings.get('message_delay', 3)}秒")

    log_path = Path("kuaishou_spark.log")
    if log_path.exists():
        size = log_path.stat().st_size
        print(f"  日志大小: {size / 1024:.1f}KB")

    print("=" * 50)
    print()


# ============================================================
# 主入口
# ============================================================

COMMANDS = {
    "login": cmd_login,
    "send": cmd_send,
    "run": cmd_run,
    "status": cmd_status,
    "config": lambda c: (save_config(c), print(f"配置文件: {CONFIG_PATH.absolute()}")),
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("可用命令:", ", ".join(COMMANDS.keys()))
        return

    command = sys.argv[1].lower()
    config = load_config()

    if command in COMMANDS:
        asyncio.run(COMMANDS[command](config))
    else:
        print(f"未知命令: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()