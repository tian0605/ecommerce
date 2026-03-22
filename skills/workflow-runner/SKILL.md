---
name: workflow-runner
description: 妙手ERP自动采集完整工作流运行器。按顺序执行6个模块：采集→提取→本地1688→落库→优化→回写，实现一键端到端采集认领。触发条件：(1)用户需要执行完整流程 (2)TC-FLOW-001端到端测试 (3)批量处理多个商品
---

# workflow-runner

妙手ERP自动采集完整工作流。按顺序执行所有模块，实现一键端到端采集认领。

## 工作流步骤

```
[步骤1] miaoshou-collector   采集并自动认领
   ↓
[步骤2] collector-scraper    提取商品主数据
   ↓
[步骤3] local-1688-weight    获取准确物流（前置）
   ↓
[步骤4] product-storer       合并数据并落库
   ↓
[步骤5] listing-optimizer    LLM优化标题描述
   ↓
[步骤6] miaoshou-updater     回写到妙手ERP
```

## 完整流程（包含采集）

```bash
cd /home/ubuntu/.openclaw/skills
python workflow_runner.py --url "https://detail.1688.com/offer/1027205078815.html"
```

## 轻量级流程（跳过采集，商品已在采集箱）

```bash
cd /home/ubuntu/.openclaw/skills
python workflow_runner.py --url "https://detail.1688.com/offer/1027205078815.html" --lightweight
```

## 批量处理

```bash
# 创建 urls.txt，每行一个1688链接
python workflow_runner.py --url-file urls.txt
```

## 模块依赖关系

```
miaoshou-collector (步骤1)
  ↓
collector-scraper (步骤2)
  ↓ ↓
  → local-1688-weight (前置) ──→ product-storer (步骤4)
                                        ↓
                               listing-optimizer (步骤5)
                                        ↓
                               miaoshou-updater (步骤6)
```

## 前置条件检查

执行工作流前，检查：
1. 妙手ERP已登录（Cookie < 24小时）
2. MobaXterm SSH隧道已建立
3. 本地1688服务已启动
4. PostgreSQL数据库可连接
5. LLM API可用

## 跳过步骤

```python
# 在 workflow_runner.py 中设置
SKIP_COLLECT = False      # 跳过采集
SKIP_OPTIMIZE = False     # 跳过优化
SKIP_UPDATE = False        # 跳过回写
```

## 输出日志

- 截图保存到各模块的 tmp 目录
- 最终结果输出到终端
- 错误时保留浏览器截图供排查

## 故障排查

| 步骤 | 常见问题 | 解决方案 |
|------|----------|----------|
| 1-采集 | Cookie过期 | 更新miaoshou_cookies.json |
| 2-提取 | 商品不在采集箱 | 先执行步骤1 |
| 3-物流 | 隧道未建立 | 建立MobaXterm隧道 |
| 4-落库 | 数据库连接失败 | 检查VPN/SSH |
| 5-优化 | LLM超时 | 重试或跳过 |
| 6-回写 | 保存失败 | 检查输入内容 |
