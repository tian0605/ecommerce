## Plan: Collector Scraper 第一批改动清单

本批次只做一件事：把 scraper 抓到的图片，按“商品主档 = 详情主图 + SKU 图片；站点页签 = 空态不展示爬虫图”的口径完整打通。范围限定为 scraper 提取、product-storer 落库、商品详情 API 聚合、商品管理页面展示四段链路。暂不开发站点级图片生成、站点级图片存储、二次优化算法。

**Steps**
1. Batch A: 抓取口径与结构稳定化。修改 [skills/collector-scraper/scraper.py](skills/collector-scraper/scraper.py) 中 `_extract_images_from_tabs`、`_extract_skus`、`scrape` 汇总段，保证输出里同时有：`main_images`、`detail_images`、`sku_images`、`skus[].image`。这里不强制改字段名，但要在内部新增“主档展示图 = main_images + detail_images”的合并规则说明。此步阻塞后续落库。
2. Batch B: 落库链路结构化。修改 [skills/product-storer/storer.py](skills/product-storer/storer.py) 中 `_upload_images_to_cos`、`store_skus` 以及主商品更新 SQL。目标是：主档展示图统一写入 products 主档图片字段，SKU 图片写入 products.sku_images 与 `product_skus.image_url`；优先复用现有字段，不做新表迁移。此步依赖 Batch A。
3. Batch C: 商品详情接口语义收敛。修改 [services/ops-api/app/queries.py](services/ops-api/app/queries.py) 中 `fetch_product` 及相关媒体回退逻辑。目标是：商品主档返回两类媒体，站点 listing 不再带入爬虫图片语义；站点页签后续只作为文案和状态展示来源。此步依赖 Batch B。
4. Batch D: 商品管理前端分层展示。修改 [apps/ops-web/src/pages/ProductManagementPage.tsx](apps/ops-web/src/pages/ProductManagementPage.tsx) 中 `buildMediaAssets`、`buildShopTabs`、媒体区域渲染。目标是：`global` 页签显示主档图片和 SKU 图片；TW/MY 等站点页签显示“待站点二次优化后生成”的空态，不显示主档素材。此步依赖 Batch C。
5. Batch E: 文档和技能说明同步。更新 [skills/collector-scraper/SKILL.md](skills/collector-scraper/SKILL.md) 和必要注释，明确当前图片职责边界与后续站点级图片规划。此步可在 Batch D 后收尾。

**按文件拆分的直接执行清单**
1. [skills/collector-scraper/scraper.py](skills/collector-scraper/scraper.py)
   目标：稳定提取 SKU 图片，并保留主图/详情图/规格图的原始分层。
   具体改动：
   - 改 `_extract_images_from_tabs`：
     - 保留现有 `main_images`、`sku_images`、`detail_images` 三类结果。
     - 增强“规格图片”页签提取的可见元素选择器，避免只抓到缩略图或漏抓变体图。
     - 增加去重规则，避免同一 SKU 图在 tab 切换后重复入池。
   - 改 `_extract_skus`：
     - 明确 `colorImages` / 规格图片映射结果如何回填到每个 SKU 的 `image` 字段。
     - 增加回退逻辑：若 1:1 映射失败，仍保留 `sku_images` 图片池，但 `skus[].image` 可为空。
     - 记录调试信息，至少包含“SKU 数量、命中的 SKU 图片映射数量、未命中 SKU 名称列表”。
   - 改 `scrape` 汇总段：
     - 输出汇总中保留 `main_images`、`detail_images`、`sku_images`。
     - 新增兼容说明字段或内部注释，说明“商品主档展示图 = main_images + detail_images”。
   验收：
   - 多 SKU 商品抓取结果中，`sku_images` 非空时，至少部分 SKU 带 `image`。
   - 无规格图商品抓取时，不因为 `skus[].image` 为空而报错。

2. [skills/product-storer/storer.py](skills/product-storer/storer.py)
   目标：把抓到的 SKU 图片真正落成主档级结构化数据，而不是只存在 JSON blob 或 COS 目录里。
   具体改动：
   - 改 `_upload_images_to_cos`：
     - 保留当前 `main_images/sku_images/detail_images` 三目录上传逻辑。
     - 返回结果里增加可用于 SKU 反写的映射结构，例如原始 URL -> COS key 或原始 URL -> COS 访问地址。
     - 定义“主档展示图”写入来源：由 `main_images + detail_images` 合并生成，排序规则明确为“主图在前，详情图在后”。
   - 改主商品存储 SQL：
     - 将 products 的主档图片字段更新为“合并后的主档展示图”。
     - 将 products.sku_images 保留为 SKU 图片池。
   - 改 `store_skus`：
     - 在 `prepared_skus` 中显式带上 `image_url`。
     - INSERT / UPDATE `product_skus` 时写入 `image_url` 列。
     - 若 COS 上传后已有新地址，则优先写 COS 地址；否则保留 scraper 原始 URL。
   验收：
   - `products.main_images` 成为主档展示图池。
   - `products.sku_images` 有 SKU 图片池。
   - `product_skus.image_url` 对有规格图的 SKU 至少部分非空。

3. [services/ops-api/app/queries.py](services/ops-api/app/queries.py)
   目标：让商品详情接口只把爬虫图片解释为“商品主档素材”，不继续在站点维度混用。
   具体改动：
   - 改 `fetch_product`：
     - 保持 `main_images` 与 `sku_images` 的回退解析能力。
     - 补齐 SKU 查询，必要时带出 `image_url`，让前端可以显示 SKU 图与 SKU 的对应关系。
     - 明确 `site_listings` 只返回站点标题、状态、更新时间等信息，不附带主档图片素材。
   - 审查 `_fetch_media_assets_for_product` 与 legacy fallback：
     - 商品主档可继续使用 `main_media_assets` / `sku_media_assets` 或 legacy 字段回退。
     - 不新增站点级媒体回退逻辑。
   验收：
   - `GET /products/{id}` 返回里，主档图片能在 `global` 页签展示。
   - `site_listings` 不携带爬虫图片语义字段。

4. [apps/ops-web/src/pages/ProductManagementPage.tsx](apps/ops-web/src/pages/ProductManagementPage.tsx)
   目标：把商品主档和站点页签的图片区彻底分层。
   具体改动：
   - 改 `buildMediaAssets`：
     - 只在 `selectedShop === 'global'` 时使用主档图片与 SKU 图片组装展示列表。
     - 标签改成新口径：主档图片区文案使用“详情主图”“SKU 图片”。
   - 改 `buildShopTabs` 和 active tab 逻辑：
     - `global` 页签固定命名为“商品主档”。
     - TW/MY 等站点页签保留。
   - 改媒体区域渲染：
     - `global` 页签：正常显示媒体预览、缩略图、上传入口。
     - 非 `global` 页签：不展示主档图，不展示 legacy 素材，显示空态文案“待站点二次优化后生成”。
     - 可选：非 `global` 页签先隐藏上传按钮，避免误导为可直接上传站点图。
   验收：
   - 商品主档能看到两类图片。
   - 切到 TW/MY 页签后，看不到爬虫抓取的素材，只看到空态。

5. [skills/collector-scraper/SKILL.md](skills/collector-scraper/SKILL.md)
   目标：把当前技能说明更新到新的图片职责边界。
   具体改动：
   - 更新“提取数据字段”章节：补充 `sku_images`、`detail_images`、`skus[].image`。
   - 更新“输出/后续模块”章节：说明图片先落商品主档，站点页签暂不使用。
   - 更新“故障排查”章节：增加“规格图片有抓到但 SKU 映射为空”的诊断办法。
   验收：
   - 新同事只读该技能文档，就能理解主档图片与站点图片的当前边界。

**Included scope**
- SKU 图片提取增强。
- 主档图片统一到“详情主图 + SKU 图片”两类。
- 商品主档显示爬虫素材。
- 站点页签显示空态，不展示爬虫素材。
- `product_skus.image_url` 打通。

**Excluded scope**
- 站点级图片生成。
- 站点级图片存储表或 listing media 表设计落地。
- 图片二次优化算法。
- 视频素材治理。
- media_assets 新表迁移作为本批次硬前提。

**Verification**
1. 用 1 个多 SKU 且有规格图的真实商品，验证 `scraper.py` 输出包含 `sku_images` 和 `skus[].image`。
2. 用同商品走 `product-storer`，验证 `products.main_images`、`products.sku_images`、`product_skus.image_url` 三处都写入成功。
3. 打开商品管理详情页，验证“商品主档”页签展示主档图片和 SKU 图片。
4. 切到 TW/MY 页签，验证图片区为空态，不再展示主档抓取图。
5. 用 1 个无规格图商品验证回退逻辑，页面无报错且主档图片正常。

**Decisions**
- 已确认：主档图片口径收敛为“详情主图 + SKU 图片”。
- 已确认：站点页签图片区保留，但只显示空态。
- 已确认：站点图片二次优化是后续功能，不纳入本批次。
- 推荐：第一批不要同时引入新的媒体表迁移，先用现有字段跑通闭环。
