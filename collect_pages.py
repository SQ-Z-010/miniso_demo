"""按 ?p=N 采集名创优品英国商城的商品列表页（第 2 页及以后）。

第 1 页由 open_shop_page.py 负责，本脚本要求 data/shop_browser.html 已存在。
每采集一页就保存该页 HTML，并把来源地址、采集时间和条数写进 data/pages.json。

用法：
    .venv\\Scripts\\python.exe collect_pages.py --pages 2 3
    .venv\\Scripts\\python.exe collect_pages.py --pages 2 --interval 15

遇到人机验证时窗口保持打开并等待人工处理，超时则保存错误记录后停止，不重试。
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://minisoshop.co.uk/shop"
DATA_DIR = Path(__file__).resolve().parent / "data"
SHOT_DIR = DATA_DIR / "shots"
PROFILE_DIR = DATA_DIR / "browser-profile"
PAGE1_HTML = DATA_DIR / "shop_browser.html"
MANIFEST = DATA_DIR / "pages.json"

CARD_SELECTORS = [
    "li.product-item",
    "ol.product-items li.item",
    "div.product-item-info",
    "ul.products li.product",
]

CHALLENGE_MARKERS = (
    "just a moment", "verify you are human", "checking your browser",
    "are you a human", "unusual traffic", "access denied",
    "enable javascript and cookies", "attention required",
    "captcha", "are you a robot",
)


def find_cards(page):
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
    for frame in page.frames:
        src = (frame.url or "").lower()
        if any(word in src for word in ("recaptcha", "turnstile", "hcaptcha", "awswaf", "captcha")):
            return True
    return False


def collect_one(page, url, page_no, max_wait):
    """打开一页并等待商品出现，返回 (卡片数, HTTP 状态, 是否超时)。"""
    status = {}
    page.on("response", lambda r: status.__setitem__("main", r.status)
            if r.url == url else None)
    print(f"\n--- 第 {page_no} 页：{url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        print(f"  首次加载未完成（继续等待）：{type(exc).__name__}")

    started = time.monotonic()
    count = 0
    while time.monotonic() - started < max_wait:
        _, count = find_cards(page)
        if count:
            break
        stamp = int(time.monotonic() - started)
        if looks_like_challenge(page):
            print(f"  [{stamp}s] 疑似人机验证，窗口保持打开，请完成后自动继续……")
        else:
            print(f"  [{stamp}s] 尚未出现商品卡片，继续等待")
        try:
            page.screenshot(path=str(SHOT_DIR / f"page{page_no}_{stamp:04d}s.png"))
        except Exception:
            pass
        time.sleep(5)
    timed_out = count == 0
    if timed_out:
        try:
            page.screenshot(path=str(SHOT_DIR / f"page{page_no}_timeout.png"))
        except Exception:
            pass
    return count, status.get("main", "未捕获"), timed_out


def main():
    parser = argparse.ArgumentParser(description="采集商品列表第 2 页及以后")
    parser.add_argument("--pages", nargs="+", type=int, default=[2, 3],
                        help="要采集的页码，例如 --pages 2 3")
    parser.add_argument("--interval", type=int, default=8,
                        help="两页之间的等待秒数，默认 8")
    parser.add_argument("--max-wait", type=int,
                        default=int(os.environ.get("BROWSER_MAX_WAIT", "300")),
                        help="单页等待人工验证的最长秒数")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)

    if not PAGE1_HTML.exists():
        print("缺少 data/shop_browser.html，请先运行 open_shop_page.py", file=sys.stderr)
        return 1
    if any(p < 2 for p in args.pages):
        print("第 1 页请用 open_shop_page.py 采集；本脚本只处理第 2 页及以后。", file=sys.stderr)
        return 1

    # 先载入已有的清单（pages.json），没有就新建，并把第 1 页登记进去。
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    known = {entry["page"]: entry for entry in manifest}
    if 1 not in known:
        known[1] = {
            "page": 1,
            "source_url": BASE_URL,
            "html_file": PAGE1_HTML.name,
            "collected_at": datetime.fromtimestamp(
                PAGE1_HTML.stat().st_mtime, tz=timezone.utc).isoformat(),
            "note": "由 open_shop_page.py 采集",
        }

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False,
            locale="en-GB", viewport={"width": 1440, "height": 900})
        page = context.new_page()

        for index, page_no in enumerate(args.pages):
            if index:
                print(f"等待 {args.interval} 秒再请求下一页……")
                time.sleep(args.interval)
            url = f"{BASE_URL}?p={page_no}"
            count, status, timed_out = collect_one(page, url, page_no, args.max_wait)
            html_path = DATA_DIR / f"shop_page{page_no}.html"
            html_path.write_text(page.content(), encoding="utf-8")
            known[page_no] = {
                "page": page_no,
                "source_url": url,
                "html_file": html_path.name,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
                "card_count": count,
                "timed_out": timed_out,
            }
            print(f"  HTTP 状态：{status}；卡片数：{count}；HTML：{html_path.name}")
            if timed_out:
                print("  超时未取得商品，停止后续页面采集（不重试）。", file=sys.stderr)
                break
        context.close()

    manifest = [known[k] for k in sorted(known)]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n清单已写入：{MANIFEST}")
    for entry in manifest:
        print(f"  第 {entry['page']} 页  HTTP {entry.get('http_status', '-')}  "
              f"卡片 {entry.get('card_count', '-')}  采集于 {entry['collected_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
