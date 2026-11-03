"""用浏览器实际验证 dashboard.html 的各项功能，不靠肉眼推断。

检查：默认统计是否与清洗结果一致、搜索筛选、品类筛选、排序、重置、
空结果提示、来源链接可达性，并监听 JS 报错。

用法：
    .venv\\Scripts\\python.exe verify_dashboard.py
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "dashboard.html"
SHOT = ROOT / "data" / "shots" / "dashboard.png"

# 与 clean_products.py 输出核对的期望值（不写死在页面里，这里独立校验）。
EXPECT = {
    "count": "106",
    "median": "£4.24",
    "discount": "99.1%",
}

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (f" —— {detail}" if detail else ""))


def main():
    if not HTML.exists():
        print("缺少 dashboard.html", file=sys.stderr)
        return 1
    SHOT.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(HTML.as_uri(), wait_until="load")

        print("【1】默认统计")
        count = page.inner_text("#kpi-count")
        median = page.inner_text("#kpi-median")
        discount = page.inner_text("#kpi-discount")
        time_txt = page.inner_text("#kpi-time")
        check("样本数量 = 106", count == EXPECT["count"], f"实际 {count}")
        check("价格中位数 = £4.24", median == EXPECT["median"], f"实际 {median}")
        check("已确认折扣占比 = 99.1%", discount == EXPECT["discount"], f"实际 {discount}")
        check("采集时间非空", "→" in time_txt, time_txt)
        den = page.inner_text("#kpi-discount-den")
        check("折扣分母含 105/106", "105/106" in den, den)

        print("\n【2】图表渲染")
        for cid in ("chart-band", "chart-cat", "chart-catprice", "chart-ip"):
            n = page.locator(f"#{cid} .bar-row").count()
            check(f"{cid} 有柱子", n > 0, f"{n} 行")

        print("\n【3】搜索筛选")
        page.fill("#f-search", "tumbler")
        n = page.locator("#tbody tr").count()
        cnt = page.inner_text("#kpi-count")
        check("搜索 tumbler 后表格行数与 KPI 一致", str(n) == cnt, f"表格 {n} / KPI {cnt}")
        check("搜索结果少于全样本", n < 106, f"{n} 条")
        names = page.locator("#tbody tr td:first-child").all_inner_texts()
        check("搜索结果均含关键词",
              all("tumbler" in t.lower() for t in names), f"{len(names)} 条")

        print("\n【4】品类与 IP 筛选")
        page.fill("#f-search", "")
        page.select_option("#f-cat", "杯壶水具")
        n_cat = page.locator("#tbody tr").count()
        check("品类筛选 = 杯壶水具 18 条", n_cat == 18, f"实际 {n_cat}")
        page.select_option("#f-cat", "")
        page.select_option("#f-ip", "Sanrio（三丽鸥）")
        n_ip = page.locator("#tbody tr").count()
        check("IP 筛选 = 三丽鸥 13 条", n_ip == 13, f"实际 {n_ip}")
        page.select_option("#f-ip", "")

        print("\n【5】排序")
        page.select_option("#f-sort", "price-asc")
        first_asc = page.inner_text("#tbody tr:first-child td:nth-child(4)")
        last_asc = page.inner_text("#tbody tr:last-child td:nth-child(4)")
        check("价格升序：首行最低 £0.59", first_asc.strip() == "£0.59", first_asc)
        check("价格升序：末行最高 £36.79", last_asc.strip() == "£36.79", last_asc)
        page.select_option("#f-sort", "price-desc")
        first_desc = page.inner_text("#tbody tr:first-child td:nth-child(4)")
        check("价格降序：首行 £36.79", first_desc.strip() == "£36.79", first_desc)
        page.click("#th-price")
        check("点击表头切换排序",
              page.inner_text("#tbody tr:first-child td:nth-child(4)").strip() == "£0.59")

        print("\n【6】重置")
        page.click("#btn-reset")
        check("重置后恢复 106 条", page.inner_text("#kpi-count") == "106",
              page.inner_text("#kpi-count"))
        check("重置后搜索框清空", page.input_value("#f-search") == "")

        print("\n【7】空结果")
        page.fill("#f-search", "zzz-不存在的商品-zzz")
        empty_visible = page.is_visible("#empty")
        empty_text = page.inner_text("#empty")
        check("显示空结果提示", empty_visible and "没有符合条件" in empty_text,
              empty_text[:40])
        check("空结果时表格区隐藏",
              page.eval_on_selector(".table-scroll", "e => e.style.display") == "none")
        check("空结果时 KPI 为 0", page.inner_text("#kpi-count") == "0")

        print("\n【8】来源链接")
        page.click("#btn-reset")
        links = page.eval_on_selector_all(
            "#tbody a[href]", "els => els.map(e => e.href)")
        check("明细表存在商品链接", len(links) >= 106, f"{len(links)} 个")
        check("链接均指向 minisoshop.co.uk",
              all("minisoshop.co.uk" in h for h in links),
              links[0] if links else "无")
        page_links = page.eval_on_selector_all(
            "#tbody td:last-child a", "els => els.map(e => e.textContent)")
        check("来源页列标注页码", all("页" in t for t in page_links),
              page_links[0] if page_links else "无")

        page.screenshot(path=str(SHOT), full_page=True)
        print(f"\n截图：{SHOT}")
        browser.close()

    print("\n【9】JS 报错")
    check("无 JS 报错", not errors, "; ".join(errors[:3]))

    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 50)
    print(f"检查项 {len(results)} 个，通过 {len(results) - len(failed)}，失败 {len(failed)}")
    for name, ok, detail in failed:
        print(f"  失败：{name} —— {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
