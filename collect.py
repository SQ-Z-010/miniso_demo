"""采集名创优品英国商城第一页；不翻页、不访问商品详情、不绕过访问限制。"""

import csv
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

URL = "https://minisoshop.co.uk/shop"
DATA_DIR = Path(__file__).resolve().parent / "data"
USER_AGENT = "MinisoLearningCollector/0.1 (educational public-product collection)"
TIMEOUT = (10, 30)  # 分别限制连接时间和读取时间，避免程序一直等待。
INTERVAL = 3  # 同一进程中，两次请求之间至少等待三秒。
FIELDS = ["name", "current_price", "original_price", "currency", "product_url", "collected_at"]
ALLOWED_HOSTS = {"minisoshop.co.uk", "www.minisoshop.co.uk"}


class CollectionError(Exception):
    """使用容易理解的错误信息停止采集。"""


class PublicClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.last_request = 0.0

    def get(self, url):
        # 手动检查重定向，防止自动请求未知站点；不重试受限请求。
        for _ in range(6):
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
                raise CollectionError(f"停止：重定向到了未允许的地址：{url}")
            time.sleep(max(0, INTERVAL - (time.monotonic() - self.last_request)))
            try:
                self.last_request = time.monotonic()
                response = self.session.get(url, timeout=TIMEOUT, allow_redirects=False)
            except requests.RequestException as exc:
                raise CollectionError(f"网络请求失败（未绕过限制）：{exc}") from exc
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise CollectionError("重定向缺少 Location，停止。")
                url = urljoin(url, location)
                continue
            if response.status_code in (401, 403, 429):
                raise CollectionError(f"访问受限：HTTP {response.status_code}，停止，不重试。")
            return response
        raise CollectionError("重定向次数过多，停止。")


def check_robots(client):
    response = client.get(urljoin(URL, "/robots.txt"))
    if response.status_code == 404:
        return  # 站点没有 robots.txt；仍遵守 HTTP 限制及请求间隔。
    if response.status_code != 200:
        raise CollectionError(f"无法确认 robots.txt 条件：HTTP {response.status_code}。")
    if "<html" in response.text.lower() or is_challenge(response.text):
        raise CollectionError("robots.txt 返回 HTML 或验证页面，停止。")
    robots = RobotFileParser()
    robots.parse(response.text.splitlines())
    if not robots.can_fetch(USER_AGENT, URL):
        raise CollectionError("robots.txt 不允许本程序访问 /shop，停止。")
    # 网站指定更长间隔时，遵循更严格的间隔。
    global INTERVAL
    delay = robots.crawl_delay(USER_AGENT)
    rate = robots.request_rate(USER_AGENT)
    INTERVAL = max(INTERVAL, delay or 0, rate.seconds / rate.requests if rate else 0)


def is_challenge(html):
    lower = html.lower()
    return any(marker in lower for marker in (
        "cf-chl-", "challenge-platform", "verify you are human", "access denied",
        "checking your browser", "unusual traffic", "just a moment...",
    ))


def text_of(node):
    return node.get_text(" ", strip=True) if node else ""


def amount(node):
    # 只抽取页面明确标出的数值，不推算折扣或原价。
    raw = text_of(node)
    match = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
    return match.group(0).replace(",", "") if match else ""


def parse_products(html, page_url, collected_at):
    soup = BeautifulSoup(html, "html.parser")
    # WooCommerce 常见列表结构。目标站实测不可达时，这些仅为待验证的兼容选择器。
    cards = soup.select("ul.products li.product, .products .product.type-product")
    if not cards:
        raise CollectionError("未找到商品卡片：页面结构可能不同、需要 JavaScript 或存在访问限制；不生成 CSV。")
    rows = []
    for card in cards:
        title = card.select_one(".woocommerce-loop-product__title, h2, h3")
        link = card.select_one("a.woocommerce-LoopProduct-link[href], a.woocommerce-loop-product__link[href]")
        if link is None and title:
            link = title.find_parent("a", href=True)
        price = card.select_one(".price")
        old = price.select_one("del .amount, del bdi") if price else None
        current = price.select_one("ins .amount, ins bdi") if price else None
        if current is None and price:
            # 区间价格不强行压成一个价格；不把划线原价误当当前价格。
            choices = [n for n in price.select(".amount") if not n.find_parent("del")]
            current = choices[0] if len(choices) == 1 else None
        symbol = text_of(price.select_one(".woocommerce-Price-currencySymbol")) if price else ""
        # £ 对应站点明确展示的英镑标记；其他未识别标记留空。
        currency = "GBP" if symbol in ("£", "GBP") else ""
        href = urljoin(page_url, link["href"]) if link else ""
        href = urldefrag(href)[0] if href else ""
        if href and urlsplit(href).scheme not in ("http", "https"):
            href = ""
        rows.append(dict(zip(FIELDS, [text_of(title), amount(current), amount(old), currency, href, collected_at])))
    return rows


def report(rows):
    links = [row["product_url"] for row in rows if row["product_url"]]
    print(f"商品数量：{len(rows)}")
    print(f"重复链接数量（多出的记录）：{len(links) - len(set(links))}")
    print(f"当前价格缺失：{sum(not row['current_price'] for row in rows)}")
    print(f"原价缺失：{sum(not row['original_price'] for row in rows)}")
    print(f"商品链接缺失：{sum(not row['product_url'] for row in rows)}")
    print("抽查前 3 条记录：")
    for row in rows[:3]:
        print(row)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = PublicClient()
    try:
        check_robots(client)
        response = client.get(URL)
        if response.status_code != 200:
            raise CollectionError(f"商品页返回 HTTP {response.status_code}，停止。")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise CollectionError("商品页不是 HTML，停止。")
        # 保存响应原始字节。即使后续解析失败，也可检查本次真实响应。
        (DATA_DIR / "shop_raw.html").write_bytes(response.content)
        if is_challenge(response.text):
            raise CollectionError("页面含访问验证或限制提示，已保存响应 HTML，停止解析。")
        collected_at = datetime.now(timezone.utc).isoformat()
        rows = parse_products(response.text, response.url, collected_at)
        # 只有成功解析才替换 CSV；失败不会用空结果覆盖以前的数据。
        temporary = DATA_DIR / "products_raw.csv.tmp"
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(DATA_DIR / "products_raw.csv")
        report(rows)
        print(f"文件已保存到：{DATA_DIR}")
        return 0
    except CollectionError as exc:
        print(f"采集未完成：{exc}", file=sys.stderr)
        print("本次未生成商品 CSV；若目录中已有文件，请核对时间，不要当作本次结果。", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"数据文件写入失败：{exc}", file=sys.stderr)
        return 1
    finally:
        client.session.close()


if __name__ == "__main__":
    sys.exit(main())
