# ERRORS.md - 错误记录

---

## [ERR-20260320-001] feishu_image_send

**Logged**: 2026-03-20T20:37:00+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
飞书发送图片失败，message工具的media参数不工作

### Error
```
channel: "feishu"
mediaUrl: "/tmp/test_1688_weight.jpg"
result: { messageId: "om_xxx", mediaUrl: "/tmp/test_1688_weight.jpg" }
# 但用户收到的是空白图片或显示失败
```

### Context
- 尝试用 message 工具的 media 参数发送截图
- 图片文件存在且格式正确（32KB, 1280x720 JPEG）
- 飞书API返回成功但用户看不到图片

### Suggested Fix
使用飞书原生API上传图片：
```python
# 1. 获取token
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal

# 2. 上传图片
POST https://open.feishu.cn/open-apis/im/v1/images
Headers: Authorization: Bearer {token}
Form: image_type=message, image=@/path/to/file.jpg
Response: { data: { image_key: "img_v3_xxx" } }

# 3. 发送图片消息
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id
Body: { receive_id: "chat_id", msg_type: "image", content: "{\"image_key\": \"img_v3_xxx\"}" }
```

### Resolution
- **Resolved**: 2026-03-20T20:37:00+08:00
- **Commit**: scripts/feishu_send_image.py
- **Notes**: 创建专用脚本封装飞书图片发送流程

### Metadata
- Reproducible: yes
- Related Files: scripts/feishu_send_image.py
- See Also: LRN-20260320-001

---
## [ERR-20260320-002] browser_relay_token

**Logged**: 2026-03-20T22:10:00+08:00
**Priority**: high
**Status**: wont_fix
**Area**: infra

### Summary
Browser Relay连接失败：Gateway token rejected

### Error
```
Gateway token rejected. Check token and save again.
```

### Context
- Chrome扩展已安装
- Gateway token配置正确（6766d8bbfe9d6e5322b6c14a20505dab5340407c2097374e）
- 但连接失败

### Root Cause
Browser Relay架构要求Chrome和Gateway在同一机器，或需要本地运行relay服务。Gateway在远程服务器，Chrome在本地，不满足此架构。

### Suggested Fix
替代方案：用户本地运行Python脚本直接采集1688数据

### Resolution
- **Resolved**: 2026-03-20T22:10:00+08:00
- **Notes**: 改用本地脚本方案，需要用户本地Python环境

### Metadata
- Reproducible: yes (架构限制)
- Related Files: scripts/feishu_send_image.py
- See Also: LRN-20260320-003

---

---
## [ERR-20260322-001] cookie_expired

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: high
**Status**: monitoring
**Area**: infra

### Summary
妙手ERP Cookies超过24小时需要更新

### Context
HEARTBEAT.md中的前置条件检查显示：
- Cookies文件存在但超过24小时
- 可能导致采集/提取失败

### Suggested Fix
提醒用户定期更新Cookie，或实现自动刷新机制

### Resolution
- **Status**: monitoring
- **Notes**: 需要用户手动更新Cookie文件

### Metadata
- Related Files: /home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json
- Tags: cookie, miaoshou, session

## 2026-03-24: collector-scraper JavaScript Execution Issues

### Problem: JavaScript in r"" strings had escaping issues
- When using `self.page.evaluate(r"""...JS code... """)`, Python's r prefix and JavaScript's backslash escaping conflicted
- Example: `\.` in JS became `\.` in Python raw string, but JS expected `.` 

### Solution
- Changed all `self.page.evaluate("""...JS...""")` to use `r"""` prefix consistently
- Used sed to batch replace: `sed -i 's/evaluate("""/evaluate(r"""/g'`

### Related Files
- `/home/ubuntu/.openclaw/skills/collector-scraper/scraper.py`

---

## 2026-03-24: JavaScript DOM Traversal - Element UI Selectors

### Learning: Element UI Dialog Structure for Miaoshou Collector
- Price input: `.jx-pro-input.price-input input.el-input__inner`
- Stock input: `.jx-pro-input input.el-input__inner` (non-price variant)
- SKU images: `.el-image.img-box .el-image__inner` (but name extraction not working)
- Stock deduplication: values appearing only once in list are true SKU stocks

### User-provided DOM Info
```html
<!-- Price -->
<div class="jx-pro-input price-input el-input el-input--small el-input--prefix">
  <input type="text" class="el-input__inner">
  <span class="el-input__prefix"><span class="price-currency">CNY</span></span>
</div>

<!-- Stock -->
<div class="jx-pro-input el-input el-input--small">
  <input type="text" class="el-input__inner">
</div>

<!-- SKU Image -->
<img class="el-image__inner" src="https://cbu01.alicdn.com/img/ibank/...">
```


## 2026-03-28 workflow_executor 技能调用问题

### 问题1: miaoshou-collector 方法名错误
**问题**: `'MiaoshouCollector' object has no attribute 'collect_and_claim_shopee'`
**根因**: workflow_executor 假设的函数名与实际不符
- 错误假设: `collect_and_claim_shopee`
- 正确方法: `collect(url_1688, wait=30)`
**解决方案**: 
1. 添加正确的方法映射
2. 构建完整的1688 URL: `f"https://detail.1688.com/offer/{product_id}.html"`
3. 同时支持从 `description` 字段提取技能名

### 问题2: collector-scraper 类名错误
**问题**: `ShopeeCollectorScraper` 类不存在
**根因**: 类名与实际文件名不符
- 错误假设: `ShopeeCollectorScraper`
- 正确类名: `CollectorScraper`
**解决方案**: 更新 SKILL_MODULES 映射表

### 问题3: miaoshou-updater 方法名错误
**问题**: `update_and_publish` 方法不存在
**根因**: 方法名与实际不符
- 错误假设: `update_and_publish`
- 正确方法: `update_product(product: Dict)`
**解决方案**: 更新为正确的类名和方法名

### 经验教训
1. **workflow_executor 调用技能前必须先检查实际的类名和方法签名**
2. **不能假设方法名**，必须对照 SKILL.md 或源代码
3. **技能信息可能在 description 字段**，fix_suggestion 可能为空
4. **商品ID需要构建完整URL**才能传递给 collector

### 预防措施
以后添加新技能到 workflow_executor 时：
1. 先 `import` 模块检查
2. 用 `dir(class_instance)` 查看所有方法
3. 用 `inspect.signature(func)` 查看方法签名

### 问题4: miaoshou_updater/collector_scraper 需要先launch浏览器
**问题**: `'NoneType' object has no attribute 'goto'`
**根因**: 调用 scrape/update 方法前未初始化浏览器
- CollectorScraper 和 MiaoshouUpdater 都有 `launch()` 方法
- 必须在使用 `self.page` 前调用 `launch()`
**解决方案**: 在 workflow_executor 中先调用 `launch()` 再调用业务方法
```python
scraper.launch()
try:
    data = scraper.scrape_product()
finally:
    scraper.close()
```

## 2026-03-28 原则：解决一类问题，不是一个问题

### 问题分类

| 问题类型 | 根因 | 系统性解决方案 |
|---------|------|---------------|
| 方法名错误 | 硬编码假设 | 每个skill暴露统一的 `run()` 方法 |
| 类名错误 | 硬编码假设 | 统一接口，不需要知道具体类名 |
| 初始化不同 | 各技能自己管理 | 初始化在skill内部完成 |
| 导入路径不同 | skill分布在不同目录 | 统一路径管理 |

### 系统性修复方案

**为每个skill添加统一的入口点：**
```python
# 每个skill的 __init__.py 暴露统一的 run() 函数
def run(product_id: str = None, **kwargs) -> dict:
    '''
    统一入口，自动处理初始化和清理
    '''
    collector = MiaoshouCollector()
    collector.launch()
    try:
        result = collector.collect(url_1688)
        return result
    finally:
        collector.close()
```

**这样workflow_executor只需要：**
```python
module = importlib.import_module(skill_module)
result = module.run(product_id='xxx')
```

### 已有技能需要修改
- miaoshou-collector: 添加 `run()` 函数
- collector-scraper: 添加 `run()` 函数  
- miaoshou-updater: 添加 `run()` 函数
- local-1688-weight: 已是函数，可直接调用

### 预防措施
以后新建skill时：
1. 在 `__init__.py` 中导出 `run()` 函数
2. 统一初始化：launch() 在 run() 内部
3. 统一清理：finally 中 close()
4. 统一返回：`{'success': bool, 'message': str, 'data': dict}`
