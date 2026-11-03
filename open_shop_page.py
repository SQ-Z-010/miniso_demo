"""用本地可见浏览器打开名创优品英国商城商品列表页。

只打开第一页，不翻页、不批量采集、不隐藏自动化痕迹。
页面出现需要人工操作的验证码时，脚本保持浏览器开着并持续等待，
由使用者在窗口里完成验证；等待超时则保存截图与 HTML 作为错误记录后退出。
"""

import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://minisoshop.co.uk/shop"
DATA_DIR = Path(__file__).resolve().parent / "data"
SHOT_DIR = DATA_DIR / "shots"
PROFILE_DIR = DATA_DIR / "browser-profile"
HTML_PATH = DATA_DIR / "shop_browser.html"
MAX_WAIT = int(os.environ.get("BROWSER_MAX_WAIT", "300"))  # 留给人工验证的时间（秒）
POLL = 5

# 待验证的候选列表选择器：Magento 与 WooCommerce 两套常见结构都列出来，
# 由脚本报告究竟哪一个命中，而不是事先假定。
CARD_SELECTORS = [
    "li.product-item",
    "ol.product-items li.item",
    "div.product-item-info",
    "ul.products li.product",
    ".products-grid .product-item",
    "li.item.product",
]

CHALLENGE_MARKERS = (
    "just a moment", "verify you are human", "checking your browser",
    "are you a human", "unusual traffic", "access denied",
    "enable javascript and cookies", "attention required",
    "captcha", "are you a robot",
)


def find_cards(page):
    """返回 (命中的选择器, 元素数量)；逐个尝试候选选择器。"""
    for selector in CARD_SELECTORS:
        try:
            count = page.locator(selector).count()
        except Exception:
            count = 0
        if count:
            return selector, count
    return None, 0


def looks_like_challenge(page):
    text = page.inner_text("body")[:4000].lower() if page.locator("body").count() else ""
    if any(marker in text for marker in CHALLENGE_MARKERS):
        return True
    # 常见的验证控件会以 iframe 形式嵌入。
    for frame in page.frames:
        src = (frame.url or "").lower()
        if any(word in src for word in ("recaptcha", "turnstile", "hcaptcha", "awswaf", "captcha")):
            return True
    return False


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    main_status = {}
    started = time.monotonic()

    with sync_playwright() as p:
        # headless=False：窗口可见，便于人工完成验证。
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            locale="en-GB",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.on("response", lambda r: main_status.__setitem__("main", r.status)
                if r.url.rstrip("/") == URL.rstrip("/") else None)

        print(f"打开页面：{URL}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print(f"首次加载未完成（继续等待人工处理）：{type(exc).__name__}: {exc}")

        selector, count = None, 0
        shot = ""
        while time.monotonic() - started < MAX_WAIT:
            selector, count = find_cards(page)
            stamp = int(time.monotonic() - started)
            shot = SHOT_DIR / f"shot_{stamp:04d}s.png"
            try:
                page.screenshot(path=str(shot))
            except Exception:
                shot = ""
            if count:
                print(f"检测到商品卡片：选择器 {selector!r}，数量 {count}")
                break
            if looks_like_challenge(page):
                print(f"[{stamp}s] 页面疑似出现人机验证，浏览器保持打开，请在窗口中完成验证……")
            else:
                print(f"[{stamp}s] 未检测到商品卡片，继续等待（截图：{shot}）")
            time.sleep(POLL)

        if not count:
            try:
                page.screenshot(path=str(SHOT_DIR / "shot_timeout.png"))
                HTML_PATH.write_text(page.content(), encoding="utf-8")
            except Exception as exc:
                print(f"保存超时记录失败：{exc}")
            print(f"等待 {MAX_WAIT} 秒后仍未取得商品列表，停止，不重试。", file=sys.stderr)
            print(f"已保存：{SHOT_DIR}、{HTML_PATH}", file=sys.stderr)
            print(f"主文档 HTTP 状态：{main_status.get('main', '未捕获')}", file=sys.stderr)
            context.close()
            return 1

        HTML_PATH.write_text(page.content(), encoding="utf-8")
        print(f"主文档 HTTP 状态：{main_status.get('main', '未捕获')}")
        print(f"页面标题：{page.title()}")
        print(f"已保存 HTML：{HTML_PATH}（{HTML_PATH.stat().st_size} 字节）")
        print(f"已保存截图：{shot}")
        print(f"命中的列表选择器：{selector!r}")

        # 打印第一张卡片的结构，用于确定真实选择器，不凭猜测写解析器。
        first = page.locator(selector).first
        html = first.inner_html()
        html = re.sub(r"\s+", " ", html)
        print("\n第一张商品卡片 HTML（截断 1800 字符）：")
        print(html[:1800])
        context.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
