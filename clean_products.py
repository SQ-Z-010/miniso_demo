"""清洗与统计：读取 data/products_raw.csv，产出 products_clean.csv 与 clean_report.txt。

原始 CSV 不会被修改或覆盖。所有判断都基于明确写死的规则：
匹配不上就标“未分类”或“未识别”，不猜、不补价格。

产出两类分类，互不影响，便于核对：
  category / category_source —— 第一版分类（站点品类优先），保留作为原始分类
  analysis_category          —— 统一分析分类（名称类型规则优先，单层互斥）

用法：
    .venv\\Scripts\\python.exe clean_products.py
"""

import csv
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW = DATA_DIR / "products_raw.csv"
CLEAN = DATA_DIR / "products_clean.csv"
REPORT = DATA_DIR / "clean_report.txt"

# ---------------------------------------------------------------------------
# 第一版分类（原始分类，保留不改）：站点品类优先，名称规则兜底。
# ---------------------------------------------------------------------------
REAL_CATEGORIES = {
    "LIFESTYLE": "生活家居",
    "BEAUTY": "美妆个护",
    "STATIONERY": "文具",
    "COLLECTIBLES": "收藏玩具",
    "GIFTS": "礼品",
    "TECHNOLOGY": "数码配件",
    "HOME ACCESSORIES": "家居饰品",
    "KITCHEN ACCESSORIES": "厨房用品",
    "BATHROOM ACCESSORIES": "浴室用品",
    "HAIR ACCESSORIES": "美发饰品",
    "BAGS & ACCESSORIES": "箱包配饰",
    "TRAVEL": "出行旅行",
    "KEYCHAINS": "钥匙扣",
}

NAME_CATEGORY_RULES_V1 = [
    ("数码配件", ["speaker", "earphone", "tws", "phone holder", "power bank", "charger"]),
    ("钥匙扣", ["keychain", "keyring", "key ring"]),
    ("出行旅行", ["travel"]),
    ("美发饰品", ["hair"]),
    ("生活家居", ["sleep mask"]),
    ("美妆个护", ["lip oil", "lip mask", "lip balm", "false nails", "mirror",
              "makeup", "cosmetic"]),
    ("服饰配件", ["socks", "cloak", "badge"]),
    ("箱包配饰", ["lunch bag", "cosmetic bag", "makeup bag", "bag", "trolley",
              "backpack", "luggage"]),
    ("餐厨用品", ["bento", "lunch box", "spoon", "chopstick", "plate", "bowl"]),
    ("杯壶水具", ["tumbler", "water bottle", "bottle", "mug", "cup", "flask"]),
    ("文具手作", ["pen", "sticker", "playing cards", "colouring", "coloring",
              "suncatcher", "plaster", "notebook", "pencil", "eraser"]),
    ("毛绒玩具", ["plush", "soft toy"]),
    ("家居饰品", ["night light", "lantern", "storage", "drawer", "cushion", "pillow"]),
    ("收藏玩具", ["wand", "figure", "blind box"]),
]

# ---------------------------------------------------------------------------
# 统一分析分类：单一层级、互斥，名称类型规则优先，站点品类只作兜底。
#
# 为什么改成名称优先：站点一级品类里 LIFESTYLE 是很大的兜底筐，
# “True Wireless Speaker Earphones”“iPhone Phone Case”“Tumbler”都被塞进去，
# 而同类商品若走名称规则却落在数码配件/杯壶水具，同一件商品两种归类。
# 名称里的类型词更贴近商品本身，所以优先采用。
# ---------------------------------------------------------------------------
ANALYSIS_RULES = [
    ("数码配件", ["speaker", "earphone", "earphones", "earbuds", "headphone", "tws",
              "phone holder", "phone case", "power bank", "charger", "cable",
              "battery", "batteries"]),
    ("钥匙扣", ["keychain", "keyring", "key ring"]),
    ("毛绒玩具", ["plush", "soft toy"]),
    ("美发饰品", ["hair"]),
    ("美妆个护", ["lip oil", "lip mask", "lip balm", "false nails", "mirror",
              "makeup", "cosmetic", "tweezer", "eyebrow", "brush set",
              "sponge", "toothbrush"]),
    ("服饰配件", ["socks", "cloak"]),
    ("箱包配饰", ["bag", "tote", "trolley", "backpack", "wallet", "luggage"]),
    ("餐厨用品", ["bento", "lunch box", "spoon", "fork", "chopstick", "plate",
              "bowl", "cutlery"]),
    ("杯壶水具", ["tumbler", "bottle", "mug", "cup", "flask"]),
    ("文具", ["pen", "pencil", "sticker", "notebook", "eraser", "paper clips",
            "playing cards", "colouring", "coloring", "suncatcher", "plaster",
            "marker"]),
    ("家居用品", ["night light", "lantern", "storage", "drawer", "cushion",
              "pillow", "towel", "lint roller", "basket"]),
    ("收藏玩具", ["wand", "figure", "blind box"]),
    ("出行旅行", ["travel"]),
    ("礼品", ["gift", "greeting card"]),
]

# 名称规则都没命中时，才把站点品类映射到同一套分析分类。
SITE_TO_ANALYSIS = {
    "LIFESTYLE": "生活家居（未细分）",
    "BEAUTY": "美妆个护",
    "STATIONERY": "文具",
    "COLLECTIBLES": "收藏玩具",
    "GIFTS": "礼品",
    "TECHNOLOGY": "数码配件",
    "HOME ACCESSORIES": "家居用品",
    "KITCHEN ACCESSORIES": "餐厨用品",
    "BATHROOM ACCESSORIES": "家居用品",
    "HAIR ACCESSORIES": "美发饰品",
    "BAGS & ACCESSORIES": "箱包配饰",
    "TRAVEL": "出行旅行",
    "KEYCHAINS": "钥匙扣",
}

# IP 识别规则：按名称关键词匹配，命中即停止。
# 注意：不能加 "apple" 作为 IP 关键词——三丽鸥有 "Apple Collection" 系列会误命中。
IP_RULES = [
    ("Sanrio（三丽鸥）", ["sanrio", "hello kitty", "cinnamoroll", "kuromi",
                     "my melody", "pompompurin", "pochacco", "keroppi",
                     "gudetama", "little twin stars", "kiki & lala"]),
    ("Disney（迪士尼）", ["disney", "stitch", "lilo", "mickey", "minnie",
                      "winnie", "pooh", "donald duck", "frozen", "toy story"]),
    ("Harry Potter（哈利波特）", ["harry potter", "hogwarts", "gryffindor", "slytherin",
                            "hufflepuff", "ravenclaw", "fantastic beasts", "niffler"]),
    ("Star Wars（星球大战）", ["star wars", "grogu", "mandalorian", "darth", "r2-d2", "yoda"]),
    ("Tom & Jerry（猫和老鼠）", ["tom & jerry", "tom and jerry", "gokko"]),
    ("One Piece（海贼王）", ["one piece", "luffy", "zoro"]),
    ("Marvel（漫威）", ["marvel", "spider-man", "spiderman", "avengers"]),
    ("We Bare Bears（咱们裸熊）", ["we bare bears", "grizzly", "ice bear"]),
    ("Care Bears（爱心小熊）", ["care bears"]),
    ("Sylvanian Families（森林家族）", ["sylvanian"]),
    ("Tamagotchi（拓麻歌子）", ["tamagotchi"]),
    ("Mofusand（猫咪三明治）", ["mofusand"]),
    ("Mikko", ["mikko"]),
    ("Peanuts（花生漫画）", ["peanuts", "snoopy"]),
    ("Barbie（芭比）", ["barbie"]),
    ("Pokemon（宝可梦）", ["pokemon", "pokémon", "pikachu"]),
    ("咒术回战", ["jujutsu kaisen"]),
    ("初音未来", ["hatsune miku", "miku"]),
    ("Mini Family（名创优品自有形象）", ["mini family", "penpen"]),
]

# 名称匹配不上时，再试站点二级品类里本身就是 IP 的词。
IP_FROM_CATEGORY2 = {
    "HARRY POTTER": "Harry Potter（哈利波特）",
    "SANRIO": "Sanrio（三丽鸥）",
    "DISNEY": "Disney（迪士尼）",
    "WE BARE BEARS": "We Bare Bears（咱们裸熊）",
}

PRICE_BANDS = [
    ("£0 – £4.99", 0, 4.99),
    ("£5 – £9.99", 5, 9.99),
    ("£10 – £14.99", 10, 14.99),
    ("£15 – £19.99", 15, 19.99),
    ("£20 – £29.99", 20, 29.99),
    ("£30 及以上", 30, float("inf")),
]
HIGH_PRICE = 100.0


def matches(name, keywords):
    """按“完整单词”匹配关键词。

    直接用 `word in name` 会误伤：关键词 pen 会命中 Pendant（吊坠），
    把毛绒挂件错判成文具。这里要求关键词前后不是字母或数字。
    """
    for word in keywords:
        if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", name):
            return True
    return False


def to_float(text):
    """字符串转小数；空值或无法解析返回 None（不猜测、不补 0）。"""
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def money(value):
    """统一价格格式：保留两位小数的字符串；空值仍留空。"""
    return "" if value is None else f"{value:.2f}"


def pick_category_v1(row):
    """第一版分类（站点品类优先），保留作为原始分类。"""
    for key in (row.get("site_category", ""), row.get("site_category2", "")):
        label = REAL_CATEGORIES.get(key.strip().upper())
        if label:
            return label, "站点品类"
    name = (row.get("name") or "").lower()
    for label, keywords in NAME_CATEGORY_RULES_V1:
        if matches(name, keywords):
            return label, "名称规则"
    return "未分类", "未判断出"


def pick_analysis_category(row):
    """统一分析分类：名称类型规则优先，站点品类兜底，都无则“未分类”。"""
    name = (row.get("name") or "").lower()
    for label, keywords in ANALYSIS_RULES:
        if matches(name, keywords):
            return label, "名称规则"
    for key in (row.get("site_category", ""), row.get("site_category2", "")):
        label = SITE_TO_ANALYSIS.get(key.strip().upper())
        if label:
            return label, "站点品类"
    return "未分类", "未判断出"


def pick_ip(row):
    """按关键词规则识别 IP；名称匹配不上再看站点二级品类。"""
    name = (row.get("name") or "").lower()
    for label, keywords in IP_RULES:
        if matches(name, keywords):
            return label
    cat2 = (row.get("site_category2") or "").strip().upper()
    if cat2 in IP_FROM_CATEGORY2:
        return IP_FROM_CATEGORY2[cat2]
    return "未识别"


def discount_status(current, original):
    """三态折扣判断。

    原价缺失时无法判断是否为折扣品，绝不能当成“未打折”。
    """
    if original is None or current is None:
        return "无法判断", ""
    if original > current:
        return "确认打折", round((original - current) / original * 100, 1)
    if original == current:
        return "确认未打折", 0.0
    return "无法判断", ""  # 原价低于现价，属异常，同样不做判断


def main():
    if not RAW.exists():
        print(f"找不到 {RAW}，请先运行 extract_shop_products.py", file=sys.stderr)
        return 1

    with RAW.open(encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))

    lines = []

    def log(text=""):
        lines.append(text)
        print(text)

    log("名创优品英国商城 商品数据清洗记录")
    log("=" * 64)
    log(f"原始文件：{RAW.name}（{len(raw_rows)} 条，本次未改动原始数据）")

    log("\n【本次口径修正记录】")
    log("1. 新增统一分析分类 analysis_category：单一层级、互斥；")
    log("   分类优先级由“站点品类优先”改为“名称类型规则优先、站点品类兜底”。")
    log("   原因：原规则把 True Wireless Speaker Earphones、iPhone Phone Case、")
    log("   Care Bears Tumbler、Tea Spoon 等归入“生活家居”，而同类商品走名称")
    log("   规则却落在数码配件/杯壶水具，同一件商品出现两种归类。")
    log("2. 折扣状态由两态改为三态：确认打折 / 确认未打折 / 无法判断。")
    log("   原价缺失一律记“无法判断”，不认定为未打折。")
    log("3. IP 规则新增 Care Bears（爱心小熊）、Mini Family（名创优品自有形象）。")
    log("   未加入 apple 关键词：三丽鸥有 Apple Collection 系列，会误命中。")
    log("4. 保留第一版分类（category + category_source）作为原始分类，未覆盖。")

    # 1) 按商品链接去重。
    seen, clean_rows, removed = set(), [], []
    for row in raw_rows:
        url = (row.get("product_url") or "").strip()
        if url and url in seen:
            removed.append(url)
            continue
        if url:
            seen.add(url)
        clean_rows.append(row)
    log(f"\n去重：删除 {len(removed)} 条重复记录，剩余 {len(clean_rows)} 条")

    # 2) 逐条清洗。
    out_rows = []
    flags_counter = Counter()
    for row in clean_rows:
        current = to_float(row.get("current_price"))
        original = to_float(row.get("original_price"))
        flags = []
        if current is None:
            flags.append("现价缺失")
        else:
            if current <= 0:
                flags.append("现价非正数")
            if current >= HIGH_PRICE:
                flags.append("高价待确认")
        if original is None:
            flags.append("原价缺失")
        elif current is not None and original < current:
            flags.append("原价低于现价")
        if not (row.get("name") or "").strip():
            flags.append("名称缺失")
        if not (row.get("product_url") or "").strip():
            flags.append("链接缺失")
        for f in flags:
            flags_counter[f] += 1

        status, pct = discount_status(current, original)
        category, category_source = pick_category_v1(row)
        analysis, analysis_source = pick_analysis_category(row)

        out_rows.append({
            "name": (row.get("name") or "").strip(),
            "category": category,
            "category_source": category_source,
            "analysis_category": analysis,
            "analysis_category_source": analysis_source,
            "ip": pick_ip(row),
            "current_price": money(current),
            "original_price": money(original),
            "currency": row.get("currency", ""),
            "discount_status": status,
            "discount_percent": pct,
            "flags": ";".join(flags),
            "product_url": row.get("product_url", ""),
            "source_page": row.get("source_page", ""),
            "collected_at": row.get("collected_at", ""),
        })

    fields = list(out_rows[0].keys()) if out_rows else []
    with CLEAN.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    log(f"\n清洗后文件：{CLEAN.name}（{len(out_rows)} 条）")
    log("标记统计：")
    if flags_counter:
        for flag, n in flags_counter.most_common():
            log(f"  {flag}：{n} 条")
    else:
        log("  无缺失或异常标记")

    # 3) 统计，分母逐项写清。
    prices = [to_float(r["current_price"]) for r in out_rows]
    prices = [p for p in prices if p is not None]
    total = len(out_rows)
    status_counter = Counter(r["discount_status"] for r in out_rows)
    discounted = status_counter.get("确认打折", 0)
    not_discounted = status_counter.get("确认未打折", 0)
    unknown = status_counter.get("无法判断", 0)
    judgeable = discounted + not_discounted

    log("\n【统计结果】")
    log("-" * 64)
    log(f"商品数量（去重后）：{total} 条  ← 全部分母")
    log(f"现价有效条数：{len(prices)} 条  ← 价格类统计的分母")
    log(f"价格中位数：£{statistics.median(prices):.2f}")
    log(f"价格均值：£{statistics.mean(prices):.2f}")
    log(f"价格区间：£{min(prices):.2f} – £{max(prices):.2f}")

    log("\n折扣状态分布（分母 = %d）：" % total)
    for label, n in (("确认打折", discounted), ("确认未打折", not_discounted),
                     ("无法判断", unknown)):
        log(f"  {label:<6} {n:>3} 条  {n / total * 100:>5.1f}%")
    log(f"  可判断商品（确认打折 + 确认未打折）：{judgeable} 条")
    log(f"  已确认折扣占全样本：{discounted}/{total} = {discounted / total * 100:.1f}%")
    if judgeable:
        log(f"  已确认折扣占可判断商品：{discounted}/{judgeable} = "
            f"{discounted / judgeable * 100:.1f}%")
    pcts = [float(r["discount_percent"]) for r in out_rows
            if r["discount_status"] == "确认打折" and r["discount_percent"] != ""]
    if pcts:
        log(f"  折扣率中位数：{statistics.median(pcts):.1f}%"
            f"（分母 = {len(pcts)} 条确认打折商品，只用有效价格记录）")

    log("\n价格带分布（分母 = 现价有效条数 %d）：" % len(prices))
    for label, low, high in PRICE_BANDS:
        n = sum(1 for p in prices if low <= p <= high)
        log(f"  {label:<12} {n:>3} 条  {n / len(prices) * 100:>5.1f}%")

    log("\n统一分析分类分布（分母 = %d）：" % total)
    for cat, n in Counter(r["analysis_category"] for r in out_rows).most_common():
        log(f"  {cat:<16} {n:>3} 条  {n / total * 100:>5.1f}%")

    log("\n各品类价格中位数（分母 = 该品类现价有效条数）：")
    by_cat = {}
    for r in out_rows:
        p = to_float(r["current_price"])
        if p is not None:
            by_cat.setdefault(r["analysis_category"], []).append(p)
    for cat, values in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        log(f"  {cat:<16} {len(values):>3} 条  中位数 £{statistics.median(values):.2f}")

    log("\n各 IP 商品数（分母 = %d）：" % total)
    for ip, n in Counter(r["ip"] for r in out_rows).most_common():
        log(f"  {ip:<24} {n:>3} 条  {n / total * 100:>5.1f}%")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n清洗记录已写入：{REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
