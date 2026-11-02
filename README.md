# 名创优品英国商城商品采集（第一阶段）

面向 Python 初学者，使用 requests 请求公开页面，使用 BeautifulSoup 解析第一页商品。代码含中文注释。本阶段不翻页、不采集详情、不制作分析页面。

## 安装与运行

需要 Python 3.10 或更新版本。在仓库目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python collect.py
```

Windows 可使用 `.venv\Scripts\python.exe` 替代 `.venv/bin/python`。不需要 API 密钥。云环境中沿用平台代理和 TLS 证书配置，不关闭证书验证。

成功退出码为 0，失败为 1。程序先检查 robots.txt，再请求商品第一页。连接超时 10 秒、读取超时 30 秒，请求之间至少间隔 3 秒；robots.txt 指定更长等待时间时遵循该要求。遇到 robots 禁止、HTTP 401/403/429、验证页面或网络错误会停止，不自动重试、不绕过限制。robots.txt 返回 404 时继续；其他无法确认的情况停止。robots.txt 不等于法律授权，运行者也应确认网站最新使用条款。

## 文件说明

- `collect.py`：请求、访问条件检查、HTML 解析、CSV 保存和质量统计。
- `requirements.txt`：固定 requests 与 beautifulsoup4 的直接依赖版本。
- `.gitignore`：排除虚拟环境、缓存、密钥配置和采集结果。
- `data/.gitkeep`：保留空数据目录。
- `data/shop_raw.html`：成功获取 HTML 响应后保存的原始字节；解析失败时仍可用于检查。HTTP 或代理限制发生在获取页面之前时不会生成。
- `data/products_raw.csv`：仅成功解析商品后生成，UTF-8 BOM 编码，方便表格软件打开。失败不覆盖旧 CSV，应核对文件时间及采集时间。

## 数据来源与字段

数据来源：<https://minisoshop.co.uk/shop>，仅第一页公开商品列表。程序不请求其他商品页面。

| 字段 | 含义 |
| --- | --- |
| name | 商品名称 |
| current_price | 当前价格，不带货币符号 |
| original_price | 页面明确展示的划线原价 |
| currency | 页面明确展示 £ 或 GBP 时记录 GBP，否则留空 |
| product_url | 商品绝对链接，移除片段标识 |
| collected_at | 本次获取商品页后的 UTC 时间，ISO 8601 格式 |

缺失字段留空；不从当前价格推算原价。价格区间暂留空，不擅自选择最低价格。保留列表中的重复记录，运行结束打印商品数量、重复链接数量（重复的多余记录数）、当前价格和原价缺失数量、链接缺失数量及前三条记录。结果是原始数据，尚未清洗。

## 已验证情况与当前限制

2026-11-02 在云环境中实际完成：

1. 创建虚拟环境，安装依赖；`python -m pip check` 通过。
2. 实际执行 `collect.py`，请求 `/robots.txt` 时平台代理返回 `CONNECT 403 Forbidden`，程序以退出码 1 停止。此错误来自环境代理，不能据此判断网站本身禁止采集。
3. 使用内存中的明确标识测试片段检查折扣价、缺失字段、区间价格、访问验证检测及无商品页面报错，均通过。这些测试片段不是实际商品，没有写入数据目录。

**未能获取实际页面，因此 robots.txt 内容、站点条款和真实 DOM 结构尚未验证。** 当前解析器使用 WooCommerce 常见结构（`ul.products li.product`、`.woocommerce-loop-product__title`、`.price`、`del` 和 `ins`），这是待实测的兼容假设，不是已确认的网站结构。实际页面结构不匹配时程序会明确报错，不生成空 CSV 冒充采集成功。

本次没有生成 `shop_raw.html` 或 `products_raw.csv`，没有真实商品数量、价格缺失统计或记录抽查结果。

目标域名 `minisoshop.co.uk` 和 `www.minisoshop.co.uk` 已加入云环境网络配置草稿。请在环境设置中审核并保存网络设置，发布环境；草稿保存本身不会应用运行时权限。访问恢复后重新执行程序，先核实网站公开访问条件，再对照原始 HTML 核实选择器及输出的前三条记录。若仍出现 403 或验证页面，应停止并检查实际错误来源，不使用代理轮换、验证码绕过或关闭 TLS 验证。
