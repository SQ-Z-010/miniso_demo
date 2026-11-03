"""从已保存的真实页面 HTML 提取商品，输出 data/products_raw.csv。

只解析本地已保存的文件，不发起网络请求。
优先读取 data/pages.json（由 open_shop_page.py / collect_pages.py 生成）来确定
要处理哪些页面、每页的来源地址和采集时间；没有清单时退回只处理第一页。

用法：
    .venv\\Scripts\\python.exe extract_shop_products.py
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent / "data"
HTML_PATH = DATA_DIR / "shop_browser.html"
MANIFEST = DATA_DIR / "pages.json"
CSV_PATH = DATA_DIR / "products_raw.csv"
# source_page、site_category* 是本项目追加的字段：前者追溯来源页，
# 后者是页面自己标注的品类（写在商品链接的 onclick 里），供清洗阶段判断品类。
FIELDS = ["name", "current_price", "original_price", "currency",
          "product_url", "collected_at", "source_page",
          "site_category", "site_category2"]


def amount(node):
    """取页面明确展示的数值；不含数值就留空，不推算、不从区间价里挑一个。"""
    if node is None:
        return ""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", node.get_text(" ", strip=True))
    return m.group(0).replace(",", "") if m else ""


def site_categories(link):
    """从商品链接的 onclick 里读取页面自带的品类（GA4 数据层）。取不到就留空。"""
    onclick = link.get("onclick", "") if link else ""
    result = []
    for key in ("item_category", "item_category2"):
        m = re.search(r'"%s":"([^"]*)"' % key, onclick)
        result.append(m.group(1).strip() if m else "")
    return result


def parse_page(html_path, page_no, collected_at):
    """解析单个页面文件，返回 (记录列表, 跳过的空壳卡片数量)。"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    cards = soup.select("li.product-item")
    rows, skipped = [], 0
    for card in cards:
        link = card.select_one("a.product-item-link[href]")
        name = link.get_text(" ", strip=True) if link else ""
        final = card.select_one('.price-wrapper[data-price-type="finalPrice"] .price')
        old = card.select_one('.price-wrapper[data-price-type="oldPrice"] .price')
        # 无名称、无价格、无链接的是模板空壳，不是商品，跳过但计数。
        if not name and final is None and link is None:
            skipped += 1
            continue
        href = (link.get("href") or "").split("#")[0] if link else ""
        symbol = card.select_one(".price")
        cat1, cat2 = site_categories(link)
        rows.append({
            "name": name,
            "current_price": amount(final),
            "original_price": amount(old),
            "currency": "GBP" if symbol and "£" in symbol.get_text() else "",
            "product_url": href if href.startswith("http") else "",
            "collected_at": collected_at,
            "source_page": page_no,
            "site_category": cat1,
            "site_category2": cat2,
        })
    return rows, skipped


def load_manifest():
    """返回 [(页码, HTML 路径, 来源地址, 采集时间)]。"""
    if MANIFEST.exists():
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
        return [(e["page"], DATA_DIR / e["html_file"],
                 e.get("source_url", ""), e.get("collected_at", ""))
                for e in sorted(entries, key=lambda x: x["page"])]
    if HTML_PATH.exists():
        return [(1, HTML_PATH, "https://minisoshop.co.uk/shop",
                 datetime.fromtimestamp(HTML_PATH.stat().st_mtime,
                                        tz=timezone.utc).isoformat())]
    return []


def main():
    pages = load_manifest()
    if not pages:
        print("找不到 data/pages.json 或 data/shop_browser.html，请先采集页面。", file=sys.stderr)
        return 1

    all_rows, per_page = [], []
    for page_no, html_path, source_url, collected_at in pages:
        if not html_path.exists():
            print(f"跳过第 {page_no} 页：文件不存在 {html_path}", file=sys.stderr)
            continue
        rows, skipped = parse_page(html_path, page_no, collected_at)
        all_rows.extend(rows)
        per_page.append((page_no, source_url, len(rows), skipped))

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    links = [r["product_url"] for r in all_rows if r["product_url"]]
    print("各页条数（已剔除空壳卡片）：")
    for page_no, source_url, n, skipped in per_page:
        print(f"  第 {page_no} 页：{n} 条（跳过空壳 {skipped}）—— {source_url}")
    print(f"\n合计记录：{len(all_rows)}")
    print(f"去重后商品数（按链接）：{len(set(links))}；多出的重复记录：{len(links) - len(set(links))}")
    print(f"当前价格缺失：{sum(not r['current_price'] for r in all_rows)}")
    print(f"原价缺失（留空不补造）：{sum(not r['original_price'] for r in all_rows)}")
    print(f"链接缺失：{sum(not r['product_url'] for r in all_rows)}")
    print(f"CSV 已写入：{CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
