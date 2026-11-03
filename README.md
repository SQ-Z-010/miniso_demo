# 名创优品英国商城商品采集（第一阶段）

面向 Python 初学者，采集名创优品英国商城商品列表的公开商品。代码含中文注释。本阶段不采集商品详情页、不制作分析页面。

站点经实测为 **Magento 2** 结构（`li.product-item`、`a.product-item-link`、`.price-wrapper[data-price-type]`），翻页为 `?p=N` 链接形式。

## 安装

需要 Python 3.10 或更新版本。在仓库目录执行（Windows 用 `.venv\Scripts\python.exe`；macOS/Linux 用 `.venv/bin/python`）：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

三步分别做什么：

1. 建虚拟环境，把依赖装在项目内，不影响系统 Python。
2. 安装 Python 包：`requests` 和 `beautifulsoup4` 负责解析，`playwright` 负责驱动浏览器。
3. 下载 Chromium 浏览器内核（约 118 MB）。**这步容易漏**：只装 `playwright` 包而不下载浏览器，运行时会报缺少可执行文件。

可用 `python -m pip check` 检查依赖是否冲突。不需要 API 密钥。

## 采集第一页（浏览器路线，当前可用）

```bash
.venv\Scripts\python.exe open_shop_page.py
```

会弹出一个**可见的浏览器窗口**访问 <https://minisoshop.co.uk/shop>。页面正常时几秒内检测到商品卡片，随即保存 HTML 与截图后关闭。

- 若出现需要人工操作的验证码：窗口保持打开，请在窗口里完成验证，脚本最长等待 300 秒（可用环境变量 `BROWSER_MAX_WAIT` 调整）。
- 等待超时：保存超时截图与 HTML 作为错误记录，退出码 1，**不自动重试**。

## 离线解析已保存的页面

```bash
.venv\Scripts\python.exe extract_shop_products.py
```

读取 `data/shop_browser.html`，不做任何网络请求，输出 `data/products_raw.csv`。好处是解析规则可以反复调整重跑，不必反复访问网站。

## 采集第 2 页及以后

```bash
.venv\Scripts\python.exe collect_pages.py --pages 2 3
```

按 `?p=N` 逐页采集，每页之间默认间隔 8 秒。第 1 页由 `open_shop_page.py` 负责；本脚本要求 `data/shop_browser.html` 已存在。每页 HTML 存为 `data/shop_page{N}.html`，来源地址与采集时间记录在 `data/pages.json`。遇到验证页或访问错误会暂停等待人工处理。

## 检查数据质量

```bash
.venv\Scripts\python.exe check_quality.py                       # 检查 data/products_raw.csv
.venv\Scripts\python.exe check_quality.py data/products_clean.csv 5
```

检查重复链接、名称缺失、价格缺失和价格异常（现价非正数、原价低于或等于现价、高价待确认），
并打印前若干条供人工与页面核对。只读文件，不修改任何数据。

## requests 路线（当前被 WAF 拦截，保留供学习）

```bash
.venv\Scripts\python.exe collect.py
```

**当前实际运行结果：失败，退出码 1。** 站点前面的 AWS WAF 对非浏览器客户端发人机验证挑战，返回 `HTTP 202` 且响应体为空，响应头带 `x-amzn-waf-action: challenge`。程序在检查 robots.txt 时即停止，不重试、不绕过。保留它是因为它展示了“先确认访问条件、失败就明确报错”的写法。

成功退出码为 0，失败为 1。连接超时 10 秒、读取超时 30 秒，请求之间至少间隔 3 秒；robots.txt 指定更长等待时间时遵循该要求。遇到 robots 禁止、HTTP 401/403/429、验证页面或网络错误会停止。robots.txt 返回 404 时继续；其他无法确认的情况停止。不关闭 TLS 证书验证。

## 清洗与统计

```bash
.venv\Scripts\python.exe clean_products.py
```

读取 `data/products_raw.csv`，产出 `data/products_clean.csv` 与 `data/clean_report.txt`，原始 CSV 保持不变。

清洗会同时产出两套分类，互不影响、便于核对：

- `category` + `category_source`：第一版分类（站点品类优先），保留作原始分类。
- `analysis_category`：**统一分析分类**，单一层级互斥，规则是"商品名称类型关键词优先、站点品类兜底"。

改成名称优先的原因：站点一级品类里 `LIFESTYLE` 是个很大的兜底筐，
`True Wireless Speaker Earphones`（耳机）、`iPhone 11 Pro Phone Case`（手机壳）、
`Care Bears Tumbler`（水杯）、`Tea Spoon`（勺子）都被塞进去，而同类商品若走名称规则
却落在数码配件/杯壶水具——同一件商品出现两种归类。名称里的类型词更贴近商品本身。

折扣状态为三态：`确认打折`（原价存在且大于现价）、`确认未打折`（原价等于现价）、
`无法判断`（原价缺失或原价低于现价的异常情形）。**原价缺失不认定为未打折。**

## 生成交互仪表盘

```bash
.venv\Scripts\python.exe build_dashboard.py      # 生成 dashboard.html
.venv\Scripts\python.exe verify_dashboard.py     # 用浏览器实际验证页面功能
```

`build_dashboard.py` 读取清洗后的 CSV，把数据、样式和脚本全部内嵌进单个
`dashboard.html`，不引用任何外部资源，**断网双击也能打开**。页面上的统计数字
全部由内嵌数据在浏览器里实时计算，生成脚本不写死任何统计结果。

`verify_dashboard.py` 用无头浏览器逐项检查：默认统计与清洗结果一致、搜索筛选、
品类/IP 筛选、价格排序、重置、空结果提示、来源链接，共 27 项，并监听 JS 报错。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `collect.py` | requests 路线：访问条件检查、HTML 解析、CSV 保存。当前被 WAF 拦截。 |
| `open_shop_page.py` | 用可见浏览器打开第一页，保存 HTML 与截图。 |
| `collect_pages.py` | 按 `?p=N` 采集第 2 页及以后，记录每页来源与时间。 |
| `extract_shop_products.py` | 离线解析各页 HTML，输出原始 CSV。 |
| `check_quality.py` | 只读检查 CSV 的重复、缺失与价格异常。 |
| `clean_products.py` | 清洗、分类与统计，输出清洗 CSV 与清洗记录。 |
| `build_dashboard.py` | 读取清洗 CSV，生成单文件交互仪表盘。 |
| `verify_dashboard.py` | 用无头浏览器逐项验证仪表盘功能。 |
| `dashboard.html` | 最终展示页面，自包含，可离线打开。 |
| `项目说明.md` | 业务问题、处理过程、实际发现、局限与 AI 参与方式。 |
| `requirements.txt` | 固定直接依赖版本。 |
| `.gitignore` | 排除虚拟环境、缓存、密钥配置和采集结果。 |
| `data/shop_browser.html` | 第一页原始 HTML（约 591 KB）。 |
| `data/shop_page{N}.html` | 第 N 页原始 HTML。 |
| `data/pages.json` | 每页的来源地址、采集时间与记录数。 |
| `data/shots/` | 每次轮询的截图，用于核对当时页面状态。 |
| `data/products_raw.csv` | 原始商品数据，UTF-8 BOM，方便表格软件打开。 |
| `data/products_clean.csv` | 清洗后数据（含原始分类与统一分析分类两套口径）。原始 CSV 不被覆盖。 |
| `data/clean_report.txt` | 清洗动作、口径修正记录与统计结果。 |
| `dashboard.html` | 单文件交互仪表盘。 |

## 数据来源与字段

数据来源：名创优品英国商城 <https://minisoshop.co.uk/shop> 的公开商品列表页，采集前若干页，不采集商品详情页。

原始 CSV 字段：

| 字段 | 含义 |
| --- | --- |
| name | 商品名称 |
| current_price | 当前价格，不带货币符号 |
| original_price | 页面明确展示的划线原价；缺失留空，**不从现价反推** |
| currency | 页面展示 £ 时记录 GBP，否则留空 |
| product_url | 商品绝对链接，移除片段标识 |
| collected_at | 获取该页 HTML 后的 UTC 时间，ISO 8601 格式 |
| source_page | 该记录来自第几页 |
| site_category / site_category2 | 页面自己标注的品类（取自商品链接的 onclick） |

清洗后 CSV 在此基础上增加 `category`（品类）、`category_source`（品类来源：站点品类 / 名称规则）、
`ip`（IP 形象）、`is_discounted`、`discount_percent`、`flags`（缺失与异常标记）。

缺失字段留空。保留列表中的重复记录，清洗阶段再按链接去重。结果是原始数据，尚未清洗。

## 已验证情况与当前限制

### 云环境（2026-11-02，失败）

在云环境中实际执行 `collect.py`：请求 `/robots.txt` 时平台代理返回 `CONNECT 403 Forbidden`，程序以退出码 1 停止。该错误来自环境代理，不能据此判断网站本身禁止采集。此时**未取得任何真实页面**。

### 本地环境（2026-11-02，成功）

1. Python 3.13.14，建虚拟环境并安装依赖，`python -m pip check` 通过。
2. 执行 `collect.py`：robots.txt 与 `/shop` 均返回 `HTTP 202`、响应头 `x-amzn-waf-action: challenge`、响应体为空——源站 AWS WAF 的人机验证挑战。退出码 1，停止。
3. 经确认改用可见浏览器（`open_shop_page.py`）：页面 `HTTP 200` 正常加载，**未出现验证码**，标题 `SHOP | MINISO`，第一页渲染 35 张卡片。
4. 第一页 35 张卡片中有 1 张是无名称、无价格、无链接的空壳模板，实际商品 **34 条**：0 条重复链接、0 条名称缺失、0 条价格缺失。前 4 条价格与页面折扣标签（-33%/-43%/-20%/-20%）交叉核对一致。
5. 翻页方式为 `?p=N` 链接（页面底部 `li.item a.page`）。采集第 2、3 页：均 `HTTP 200`，每页 37 张卡片、各剔除 1 张空壳，得 36 条。三页合计 **106 条**，按链接去重后仍是 106 条（0 条重复），现价缺失 0 条，原价缺失 1 条（未打折商品，留空不补造）。
6. 清洗后统计（分母 = 去重后 106 条）：价格中位数 £4.24，均值 £6.03，区间 £0.59 – £36.79；可确认折扣商品 105 条，占 99.1%。详见 `data/clean_report.txt`。
7. 品类来源：35.8% 来自页面自带品类，64.2% 由商品名称关键词推断（页面一级品类 `BY BRAND` 是导航词，不能直接当品类名）。两套口径粒度不同，横向比较要留意。
8. **口径修正**：抽查发现"站点品类优先"导致耳机、手机壳、水杯、勺子被归入"生活家居"，
   且同款商品出现两种归类。新增统一分析分类 `analysis_category`（名称类型规则优先、
   站点品类兜底），保留原始分类未覆盖；折扣状态改为三态（确认打折/确认未打折/无法判断），
   原价缺失不认定为未打折；IP 规则新增 Care Bears、Mini Family。
   修正后：106 条全部归入 13 个统一品类，`生活家居（未细分）` 与 `未分类` 均为 0 条。
9. **仪表盘验证**：`verify_dashboard.py` 用无头 Chromium 实际打开 `dashboard.html`，
   27 项检查全部通过（默认统计 106/£4.24/99.1% 与清洗结果一致、搜索、品类与 IP 筛选、
   价格排序与表头点击、重置、空结果提示、来源链接均指向 minisoshop.co.uk、无 JS 报错）。

### 样本范围的说明

本次只采集**前 3 页共 106 条**，页面标注全站约 233 条商品，因此**不覆盖全站**。
第 1–3 页按“推荐”排序，哈利波特系列占 55.7%，样本结构不代表全站结构，
价格与品类的统计结论只能在“前 3 页样本”范围内解读。

### 仍未确认的事项

- **robots.txt 内容、站点使用条款至今没有读到。** 云环境代理 403、本地请求被 WAF 挑战，两种路线都没能取得 robots.txt 正文。浏览器路线**没有执行 robots.txt 检查**，运行者应自行打开 <https://minisoshop.co.uk/robots.txt> 与站点条款确认是否允许采集，并自行控制采集频率。
- 浏览器路线能打开页面，只说明页面对真人可见，**不等于取得了采集授权**。
- 不使用代理轮换、验证码绕过或关闭 TLS 验证。
- 前一版 README 假定站点是 WooCommerce（选择器 `ul.products li.product`），实测为 Magento 2，该假设已修正。
- 页面标注商品总数约 233 条，本项目只采集前若干页，**不宣称覆盖全站**。

## 复现时的核对建议

1. 打开 `data/shots/` 里最新截图，确认当时页面正常、没有验证提示。
2. 对照 `data/shop_browser.html` 检查选择器是否仍然命中（站点改版会失效）。
3. 抽查 CSV 前几条，与页面上的名称和价格逐项比对。
4. 核对 `data/products_raw.csv` 的修改时间，不要用旧文件充当本次结果。
