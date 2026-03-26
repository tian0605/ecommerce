# KNOWLEDGE.md - 知识库

> 记录成功案例、技巧和最佳实践

---

## ✅ 成功案例 #success

### SSH隧道绕过1688 IP反爬
**日期：** 2026-03-22
**问题：** 1688商品页面触发IP反爬，无法直接获取重量数据
**方案：** 在本地Windows机器运行Flask服务，通过SSH隧道访问
**结果：** 成功获取准确重量/尺寸数据，绕过IP限制
**关键配置：**
```bash
# SSH隧道
ssh -L 8080:127.0.0.1:8080 user@remote_server
# 本地服务端口：8080
# 远程调用：http://127.0.0.1:8080/get_weight?url=xxx
```

### 妙手ERP虚拟表格数据提取
**日期：** 2026-03-20
**问题：** 妙手ERP使用Vue虚拟表格组件，无法用传统table选择器
**方案：** 从输入框placeholder和value中提取规格数据
**结果：** 成功提取SKU、规格、价格等信息
**关键代码：**
```python
# 从输入框提取规格
for inp in inputs:
    ph = inp.get_attribute('placeholder') or ''
    val = inp.input_value() or ''
    if '请输入规格名称' == ph:
        current_spec_name = val
```

### LLM Listing优化繁体化
**日期：** 2026-03-25
**问题：** 商品描述需要从简体中文转换为繁体中文，符合台湾市场
**方案：** 使用qwen-plus模型，提示词要求结构化输出+emoji
**结果：** 优化后描述可读性大幅提升，符合台湾消费者习惯
**模型配置：**
```python
LLM_MODEL = 'qwen-plus'
temperature = 0.7
max_tokens = 1500
```

---

## 💡 技巧 #tip

### 快速检查前置条件
```bash
bash /root/.openclaw/workspace-e-commerce/scripts/check-preconditions.sh
```

### 查看数据库待处理商品
```python
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', 
                        user='superuser', password='Admin123!')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM products WHERE status = 'collected'")
print(f'待处理: {cur.fetchone()[0]}')
```

### 避免Playwright线程冲突
```python
# 启动浏览器时使用threaded=False
browser = await playwright.chromium.launch(threaded=False)
```

### 妙手Cookies刷新
当采集返回空或失败时，先检查Cookies是否过期：
```bash
# 检查Cookies文件修改时间
ls -la /home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json
# 如果超过24小时，需要重新导出
```

### 数据库enum类型查询
```python
import psycopg2
conn = psycopg2.connect(...)
cur = conn.cursor()
cur.execute("""
    SELECT enumlabel FROM pg_enum 
    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'product_status')
""")
print(cur.fetchall())
```

---

## 🎯 最佳实践

### 1. 模块独立性
每个skill模块应独立可运行，便于测试和调试

### 2. 日志分级
- INFO：正常流程
- WARNING：异常但可恢复
- ERROR：需要关注的问题

### 3. 错误处理
- 先判断是否有标准解决流程
- 记录到ERRORS.md
- 再分析根本原因

### 4. 数据库操作
- 使用context manager确保连接释放
- 避免直接更新status（可能有enum限制）
- 先SELECT确认数据存在

### 5. API调用
- 设置合理timeout
- 记录完整请求/响应
- 失败时保留现场便于调试

---

*最后更新：2026-03-25 11:08*
