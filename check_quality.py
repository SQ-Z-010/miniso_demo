"""检查商品 CSV 的数据质量：重复链接、缺失字段、价格异常。

只读本地 CSV，不做网络请求，也不修改任何文件。
用法：
    .venv\\Scripts\\python.exe check_quality.py                    # 检查 data/products_raw.csv
    .venv\\Scripts\\python.exe check_quality.py data/other.csv 10  # 指定文件与前几条
"""

import csv
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
HIGH_PRICE = 100.0  # 超过这个数目标记为“高价待确认”，不一定是错误


def to_float(text):
    """把字符串转成小数；无法转换时返回 None，绝不猜测数值。"""
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "products_raw.csv"
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    if not path.exists():
        print(f"找不到文件：{path}", file=sys.stderr)
        return 1

    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    print(f"检查文件：{path}")
    print(f"记录总数：{len(rows)}")
    print()

    # 1) 重复链接：同一个商品被重复列出的次数（多出来的条数）。
    urls = [r.get("product_url", "").strip() for r in rows]
    filled = [u for u in urls if u]
    dup = [u for u, n in Counter(filled).items() if n > 1]
    print(f"链接缺失：{len(urls) - len(filled)}")
    print(f"重复链接种类：{len(dup)}；多出的记录数：{len(filled) - len(set(filled))}")
    for u in dup[:5]:
        print(f"  重复：{u}")

    # 2) 名称缺失。
    no_name = [r for r in rows if not (r.get("name") or "").strip()]
    print(f"\n名称缺失：{len(no_name)}")
    for r in no_name[:5]:
        print(f"  缺名称：{r.get('product_url', '')}")

    # 3) 价格缺失：现价是分析的主字段，缺失必须记录。
    no_current = [r for r in rows if to_float(r.get("current_price")) is None]
    no_original = [r for r in rows if not (r.get("original_price") or "").strip()]
    print(f"\n现价缺失或无法解析：{len(no_current)}")
    for r in no_current[:5]:
        print(f"  缺现价：{(r.get('name') or '')[:60]}")
    # 原价缺失是正常情况（未打折商品本来就没有划线价），只报告数量，不补造。
    print(f"原价缺失（未打折商品，留空不补造）：{len(no_original)}")

    # 4) 价格异常。
    anomalies = []
    for index, r in enumerate(rows, start=1):
        cur = to_float(r.get("current_price"))
        old = to_float(r.get("original_price"))
        name = (r.get("name") or "")[:50]
        if cur is not None and cur <= 0:
            anomalies.append((index, name, f"现价非正数：{r.get('current_price')}"))
        if cur is not None and cur >= HIGH_PRICE:
            anomalies.append((index, name, f"高价待确认：{cur}"))
        if cur is not None and old is not None and old < cur:
            anomalies.append((index, name, f"原价低于现价：原价 {old} < 现价 {cur}"))
        if cur is not None and old is not None and old == cur:
            anomalies.append((index, name, f"原价等于现价：{old}（实际未打折）"))
    print(f"\n价格异常条目：{len(anomalies)}")
    for index, name, why in anomalies[:20]:
        print(f"  第 {index} 行 {name} —— {why}")

    # 5) 抽查前若干条，供人工与页面核对。
    print(f"\n前 {top_n} 条记录：")
    for i, r in enumerate(rows[:top_n], start=1):
        print(f"{i:>2}. {(r.get('name') or '').strip()}")
        print(f"    现价 £{r.get('current_price', '')}  原价 £{r.get('original_price', '') or '（无）'}")
        print(f"    {r.get('product_url', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
