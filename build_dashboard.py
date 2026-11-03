"""生成单文件交互仪表盘 dashboard.html。

读取 data/products_clean.csv，把数据和样式、脚本全部内嵌进一个 HTML 文件，
不引用任何外部资源，断网双击也能打开。页面上的所有统计都由内嵌数据实时算出，
脚本不写死任何统计数字。

用法：
    .venv\\Scripts\\python.exe build_dashboard.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
CLEAN = DATA_DIR / "products_clean.csv"
OUTPUT = Path(__file__).resolve().parent / "dashboard.html"

TITLE = "名创优品英国线上商品观察"
SUBTITLE = "前3页商品样本的结构、价格带与折扣分析"


def to_number(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_records():
    import csv
    with CLEAN.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    records = []
    for row in rows:
        records.append({
            "n": row.get("name", ""),
            "c": row.get("analysis_category", ""),   # 统一分析分类
            "oc": row.get("category", ""),           # 原始分类（保留）
            "cs": row.get("analysis_category_source", ""),
            "ip": row.get("ip", ""),
            "cp": to_number(row.get("current_price")),
            "op": to_number(row.get("original_price")),
            "st": row.get("discount_status", ""),
            "dp": to_number(row.get("discount_percent")),
            "u": row.get("product_url", ""),
            "p": row.get("source_page", ""),
            "t": row.get("collected_at", ""),
        })
    return records


def build_html(records):
    # 转义 "</" 防止提前闭合 script 标签。
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return TEMPLATE.replace("__TITLE__", TITLE) \
                   .replace("__SUBTITLE__", SUBTITLE) \
                   .replace("__DATA__", payload) \
                   .replace("__GENERATED__", generated)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{
    --bg:#f6f7f9; --card:#ffffff; --line:#e5e7eb; --ink:#111827; --ink2:#4b5563;
    --ink3:#6b7280; --accent:#2563eb; --accent-soft:#dbeafe; --warn:#b45309;
    --warn-soft:#fef3c7; --ok:#047857; --ok-soft:#d1fae5; --neutral:#e5e7eb;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
    "Hiragino Sans GB","Microsoft YaHei",sans-serif;line-height:1.6}
  .wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
  header{margin-bottom:22px}
  h1{margin:0 0 6px;font-size:26px;letter-spacing:.5px}
  .sub{margin:0;color:var(--ink2);font-size:15px}
  .meta{margin-top:10px;color:var(--ink3);font-size:13px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:18px 20px;margin-bottom:16px}
  h2{margin:0 0 14px;font-size:16px;font-weight:600}
  .hint{color:var(--ink3);font-size:12px;margin:-8px 0 14px}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
  .kpi .k-label{font-size:12px;color:var(--ink3)}
  .kpi .k-value{font-size:26px;font-weight:600;margin:4px 0 2px}
  .kpi .k-den{font-size:11px;color:var(--ink3)}
  .filters{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end}
  .field{display:flex;flex-direction:column;gap:4px}
  .field label{font-size:12px;color:var(--ink3)}
  input[type=text],select{font:inherit;font-size:14px;padding:7px 10px;
    border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}
  input[type=text]{min-width:230px}
  button{font:inherit;font-size:14px;padding:8px 14px;border-radius:8px;
    border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer}
  button:hover{background:var(--accent-soft);border-color:var(--accent)}
  .charts{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media (max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}
    .charts{grid-template-columns:1fr}}
  .bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:13px}
  .bar-label{flex:0 0 116px;color:var(--ink2);overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}
  .bar-track{flex:1;background:var(--neutral);border-radius:6px;height:16px;overflow:hidden}
  .bar-fill{height:100%;background:var(--accent);border-radius:6px;min-width:2px}
  .bar-fill.alt{background:#7c3aed}
  .bar-fill.green{background:var(--ok)}
  .bar-value{flex:0 0 106px;text-align:right;color:var(--ink3);font-variant-numeric:tabular-nums}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:12px;color:var(--ink3);font-weight:600;background:#fafafa;
    position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap}
  th:hover{color:var(--accent)}
  td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  tbody tr:hover{background:#f9fafb}
  .table-scroll{max-height:560px;overflow-y:auto;border:1px solid var(--line);border-radius:10px}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;white-space:nowrap}
  .tag.ok{background:var(--ok-soft);color:var(--ok)}
  .tag.warn{background:var(--warn-soft);color:var(--warn)}
  .tag.gray{background:var(--neutral);color:var(--ink2)}
  .empty{padding:30px;text-align:center;color:var(--ink3);font-size:14px}
  .empty strong{display:block;color:var(--ink2);margin-bottom:6px;font-size:15px}
  footer{color:var(--ink3);font-size:12.5px}
  footer h3{font-size:14px;color:var(--ink2);margin:0 0 8px}
  footer ul{margin:0 0 14px;padding-left:20px}
  footer li{margin-bottom:5px}
  .count-line{font-size:13px;color:var(--ink2);margin-bottom:10px}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>__TITLE__</h1>
  <p class="sub">__SUBTITLE__</p>
  <p class="meta">数据来源：minisoshop.co.uk 商品列表页前 3 页 ｜ 页面生成时间：__GENERATED__ ｜
     全部统计由页面内嵌数据实时计算</p>
</header>

<section class="kpis">
  <div class="kpi"><div class="k-label">样本数量（当前筛选）</div>
    <div class="k-value" id="kpi-count">–</div>
    <div class="k-den" id="kpi-count-den"></div></div>
  <div class="kpi"><div class="k-label">采集时间（UTC）</div>
    <div class="k-value" id="kpi-time" style="font-size:17px">–</div>
    <div class="k-den">取当前筛选结果的最早与最晚采集时间</div></div>
  <div class="kpi"><div class="k-label">价格中位数</div>
    <div class="k-value" id="kpi-median">–</div>
    <div class="k-den" id="kpi-median-den"></div></div>
  <div class="kpi"><div class="k-label">已确认折扣商品占比</div>
    <div class="k-value" id="kpi-discount">–</div>
    <div class="k-den" id="kpi-discount-den"></div></div>
</section>

<section class="card">
  <h2>筛选与排序</h2>
  <p class="hint">下方所有指标、图表和明细表都会随筛选同步更新。</p>
  <div class="filters">
    <div class="field"><label for="f-search">商品名称搜索</label>
      <input type="text" id="f-search" placeholder="输入关键词，如 tumbler"></div>
    <div class="field"><label for="f-cat">统一品类</label><select id="f-cat"></select></div>
    <div class="field"><label for="f-ip">IP 形象</label><select id="f-ip"></select></div>
    <div class="field"><label for="f-st">折扣状态</label><select id="f-st"></select></div>
    <div class="field"><label for="f-sort">排序</label><select id="f-sort">
      <option value="price-asc">价格：从低到高</option>
      <option value="price-desc">价格：从高到低</option>
      <option value="discount-desc">折扣率：从高到低</option>
      <option value="name-asc">名称：A → Z</option>
    </select></div>
    <button id="btn-reset">重置筛选</button>
  </div>
</section>

<section class="charts">
  <div class="card"><h2>价格带分布</h2>
    <p class="hint" id="hint-band"></p><div id="chart-band"></div></div>
  <div class="card"><h2>统一品类分布</h2>
    <p class="hint" id="hint-cat"></p><div id="chart-cat"></div></div>
  <div class="card"><h2>各品类价格中位数</h2>
    <p class="hint" id="hint-catprice"></p><div id="chart-catprice"></div></div>
  <div class="card"><h2>IP 分布</h2>
    <p class="hint" id="hint-ip"></p><div id="chart-ip"></div></div>
</section>

<section class="card">
  <h2>商品明细</h2>
  <p class="count-line" id="table-count"></p>
  <div class="table-scroll">
    <table id="table">
      <thead><tr>
        <th id="th-name">商品名称（点击访问来源页面）</th>
        <th id="th-cat">统一品类</th>
        <th>IP</th>
        <th id="th-price">现价</th>
        <th>原价</th>
        <th id="th-discount">折扣率</th>
        <th>折扣状态</th>
        <th>来源页</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <div id="empty" class="empty" style="display:none"></div>
</section>

<footer class="card">
  <h3>说明</h3>
  <ul>
    <li><strong>数据来源</strong>：名创优品英国商城商品列表页
      <a href="https://minisoshop.co.uk/shop" target="_blank" rel="noopener">minisoshop.co.uk/shop</a>
      的前 3 页（<code>/shop</code>、<code>/shop?p=2</code>、<code>/shop?p=3</code>），
      由本地可见浏览器采集，仅取列表页公开信息，未采集商品详情页。</li>
    <li><strong>分类方法</strong>：统一分析分类采用“商品名称类型关键词优先、站点自带品类兜底”，
      单一层级互斥；原始分类（站点品类优先那一版）在明细表中保留，可对照。
      IP 依据名称关键词识别，判断不出的一律标“未识别”，不猜测。</li>
    <li><strong>统计分母</strong>：占比类指标分母为当前筛选后的样本数；
      价格类指标分母为现价有效的样本数；折扣率只对“确认打折”的商品计算；
      原价缺失一律记“无法判断”，不认定为未打折，也不反推原价。</li>
    <li><strong>样本局限</strong>：本次仅采集前 3 页共 106 条，页面标注全站约 233 条，
      <strong>不覆盖全站</strong>；前 3 页为站点“推荐”排序结果，哈利波特系列占比偏高，
      样本结构不代表全站结构。所有结论仅限本次样本，
      <strong>不推断销量、利润、爆款或消费者偏好</strong>。</li>
    <li><strong>合规提示</strong>：站点 robots.txt 与使用条款在本次采集中未能取得正文，
      运行者应自行确认是否允许采集。</li>
  </ul>
</footer>

</div>

<script>
const DATA = __DATA__;

const BANDS = [
  {label:"£0 – £4.99", lo:0, hi:4.99},
  {label:"£5 – £9.99", lo:5, hi:9.99},
  {label:"£10 – £14.99", lo:10, hi:14.99},
  {label:"£15 – £19.99", lo:15, hi:19.99},
  {label:"£20 – £29.99", lo:20, hi:29.99},
  {label:"£30 及以上", lo:30, hi:Infinity}
];

const money = v => (v === null || v === undefined) ? "—" : "£" + v.toFixed(2);
const pctText = (a, b) => b === 0 ? "—" : (a / b * 100).toFixed(1) + "%";

function median(nums){
  if(!nums.length) return null;
  const s = [...nums].sort((a,b)=>a-b);
  const m = Math.floor(s.length/2);
  return s.length % 2 ? s[m] : (s[m-1] + s[m]) / 2;
}

function groupCount(rows, key){
  const map = new Map();
  rows.forEach(r => map.set(r[key], (map.get(r[key]) || 0) + 1));
  return [...map.entries()].sort((a,b) => b[1] - a[1]);
}

function fillSelect(el, values, allLabel){
  el.innerHTML = "";
  const opt = document.createElement("option");
  opt.value = ""; opt.textContent = allLabel;
  el.appendChild(opt);
  values.forEach(v => {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    el.appendChild(o);
  });
}

function renderBars(container, items, valueText, cls){
  if(!items.length){ container.innerHTML = '<div class="empty">当前筛选无数据</div>'; return; }
  const max = Math.max(...items.map(i => i.value));
  container.innerHTML = items.map(i => {
    const w = max > 0 ? (i.value / max * 100) : 0;
    return '<div class="bar-row">'
      + '<span class="bar-label" title="' + i.label + '">' + i.label + '</span>'
      + '<div class="bar-track"><div class="bar-fill ' + (cls||"") + '" style="width:' + w.toFixed(1) + '%"></div></div>'
      + '<span class="bar-value">' + valueText(i) + '</span></div>';
  }).join("");
}

function currentRows(){
  const q = document.getElementById("f-search").value.trim().toLowerCase();
  const cat = document.getElementById("f-cat").value;
  const ip = document.getElementById("f-ip").value;
  const st = document.getElementById("f-st").value;
  let rows = DATA.filter(r =>
    (!q || r.n.toLowerCase().includes(q)) &&
    (!cat || r.c === cat) &&
    (!ip || r.ip === ip) &&
    (!st || r.st === st)
  );
  const sort = document.getElementById("f-sort").value;
  rows.sort((a,b) => {
    if(sort === "price-asc")  return (a.cp ?? Infinity) - (b.cp ?? Infinity);
    if(sort === "price-desc") return (b.cp ?? -1) - (a.cp ?? -1);
    if(sort === "discount-desc") return (b.dp ?? -1) - (a.dp ?? -1);
    return a.n.localeCompare(b.n);
  });
  return rows;
}

function render(){
  const rows = currentRows();

  // KPI
  const total = rows.length;
  const withPrice = rows.filter(r => r.cp !== null);
  const med = median(withPrice.map(r => r.cp));
  const discounted = rows.filter(r => r.st === "确认打折").length;
  const judgeable = rows.filter(r => r.st === "确认打折" || r.st === "确认未打折").length;

  document.getElementById("kpi-count").textContent = total;
  document.getElementById("kpi-count-den").textContent =
    "全样本 " + DATA.length + " 条";

  const times = rows.map(r => r.t).filter(Boolean).sort();
  document.getElementById("kpi-time").textContent = times.length
    ? times[0].slice(0,16).replace("T"," ") + " → " + times[times.length-1].slice(11,16)
    : "—";
  document.getElementById("kpi-time").nextElementSibling.textContent = times.length
    ? "起始 " + times[0].slice(0,10) + "，仅本次采集窗口"
    : "当前筛选无采集时间";

  document.getElementById("kpi-median").textContent = money(med);
  document.getElementById("kpi-median-den").textContent =
    "分母 = 现价有效 " + withPrice.length + " 条（" + money(Math.min(...withPrice.map(r=>r.cp)))
    + " – " + money(Math.max(...withPrice.map(r=>r.cp))) + "）";

  document.getElementById("kpi-discount").textContent = pctText(discounted, total);
  document.getElementById("kpi-discount-den").textContent =
    discounted + "/" + total + " 条；占可判断商品 "
    + (judgeable ? pctText(discounted, judgeable) : "—") + "（可判断 " + judgeable + " 条）";

  // 图表
  const bandItems = BANDS.map(b => ({
    label: b.label,
    value: withPrice.filter(r => r.cp >= b.lo && r.cp <= b.hi).length
  }));
  document.getElementById("hint-band").textContent =
    "分母 = 现价有效 " + withPrice.length + " 条";
  renderBars(document.getElementById("chart-band"), bandItems,
    i => i.value + " 条 · " + pctText(i.value, withPrice.length));

  const catItems = groupCount(rows, "c").map(([k,v]) => ({label:k, value:v}));
  document.getElementById("hint-cat").textContent = "分母 = " + total + " 条";
  renderBars(document.getElementById("chart-cat"), catItems,
    i => i.value + " 条 · " + pctText(i.value, total), "alt");

  const catPrice = {};
  withPrice.forEach(r => (catPrice[r.c] = catPrice[r.c] || []).push(r.cp));
  const catPriceItems = Object.entries(catPrice)
    .map(([k,v]) => ({label:k, value:median(v), n:v.length}))
    .sort((a,b) => b.value - a.value);
  document.getElementById("hint-catprice").textContent =
    "按中位数由高到低；柱长按最大值等比缩放";
  renderBars(document.getElementById("chart-catprice"), catPriceItems,
    i => money(i.value) + " (" + i.n + ")");

  const ipItems = groupCount(rows, "ip").map(([k,v]) => ({label:k, value:v}));
  document.getElementById("hint-ip").textContent =
    "分母 = " + total + " 条；保留“未识别”";
  renderBars(document.getElementById("chart-ip"), ipItems,
    i => i.value + " 条 · " + pctText(i.value, total), "green");

  // 明细表
  document.getElementById("table-count").textContent =
    "当前显示 " + rows.length + " 条（全样本 " + DATA.length + " 条）";
  const tbody = document.getElementById("tbody");
  const empty = document.getElementById("empty");
  if(!rows.length){
    tbody.innerHTML = "";
    empty.style.display = "block";
    empty.innerHTML = "<strong>没有符合条件的商品</strong>"
      + "请尝试清空搜索词，或把品类 / IP / 折扣状态改回“全部”，"
      + "也可以点击“重置筛选”恢复全样本。";
    document.querySelector(".table-scroll").style.display = "none";
    return;
  }
  empty.style.display = "none";
  document.querySelector(".table-scroll").style.display = "block";
  const tagCls = s => s === "确认打折" ? "ok" : (s === "无法判断" ? "warn" : "gray");
  tbody.innerHTML = rows.map(r => {
    const nameCell = r.u
      ? '<a href="' + r.u + '" target="_blank" rel="noopener">' + r.n + "</a>"
      : r.n;
    return "<tr>"
      + "<td>" + nameCell + "</td>"
      + '<td title="原始分类：' + r.oc + '">' + r.c + "</td>"
      + "<td>" + r.ip + "</td>"
      + '<td class="num">' + money(r.cp) + "</td>"
      + '<td class="num">' + (r.op === null ? "—" : money(r.op)) + "</td>"
      + '<td class="num">' + (r.st === "确认打折" ? r.dp.toFixed(1) + "%" : "—") + "</td>"
      + '<td><span class="tag ' + tagCls(r.st) + '">' + r.st + "</span></td>"
      + '<td><a href="https://minisoshop.co.uk/shop' + (r.p === "1" ? "" : "?p=" + r.p)
      + '" target="_blank" rel="noopener">第 ' + r.p + " 页</a></td>"
      + "</tr>";
  }).join("");
}

function init(){
  fillSelect(document.getElementById("f-cat"),
    [...new Set(DATA.map(r => r.c))].sort(), "全部品类");
  fillSelect(document.getElementById("f-ip"),
    [...new Set(DATA.map(r => r.ip))].sort(), "全部 IP");
  fillSelect(document.getElementById("f-st"),
    [...new Set(DATA.map(r => r.st))].sort(), "全部状态");

  ["f-search","f-cat","f-ip","f-st","f-sort"].forEach(id =>
    document.getElementById(id).addEventListener("input", render));
  document.getElementById("btn-reset").addEventListener("click", () => {
    document.getElementById("f-search").value = "";
    ["f-cat","f-ip","f-st"].forEach(id => document.getElementById(id).value = "");
    document.getElementById("f-sort").value = "price-asc";
    render();
  });
  document.getElementById("th-price").addEventListener("click", () => {
    const sel = document.getElementById("f-sort");
    sel.value = sel.value === "price-asc" ? "price-desc" : "price-asc";
    render();
  });
  document.getElementById("th-discount").addEventListener("click", () => {
    document.getElementById("f-sort").value = "discount-desc"; render();
  });
  document.getElementById("th-name").addEventListener("click", () => {
    document.getElementById("f-sort").value = "name-asc"; render();
  });
  render();
}
init();
</script>
</body>
</html>
"""


def main():
    if not CLEAN.exists():
        print(f"找不到 {CLEAN}，请先运行 clean_products.py", file=sys.stderr)
        return 1
    records = load_records()
    OUTPUT.write_text(build_html(records), encoding="utf-8")
    print(f"已生成：{OUTPUT}（{OUTPUT.stat().st_size} 字节，嵌入 {len(records)} 条记录）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
