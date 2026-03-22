# HEARTBEAT.md - CommerceFlow 运营监控

---

## ⚠️ 工作流前置条件检查（每次工作前必查）

**参考文档：** `docs/preconditions-checklist.md`

### 三个必要条件

| 条件 | 检查方法 | 处理 |
|------|----------|------|
| 1. 妙手ERP已登录 | Cookies文件存在且<24小时 | `/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json` |
| 2. 本地爬虫服务启用 | `curl http://127.0.0.1:9090/health` 返回OK | 重启 `python local-1688-weight-server.py` |
| 3. SSH隧道打开 | `ss -tlnp \| grep 9090` 显示LISTEN | 重建MobaXterm隧道 |

**快速检查命令：**
```bash
/root/.openclaw/workspace-e-commerce/scripts/check-preconditions.sh
```

---

# 每日定期检查任务

## 每日任务 (按顺序轮询)

### 工作日 09:00
- [ ] 采集昨日核心运营数据
- [ ] 生成每日运营日报
- [ ] 检查库存预警
- [ ] 检查价格异常

### 工作日 14:00
- [ ] 监控营销活动效果
- [ ] 检查退款/异常订单

### 每日 18:00
- [ ] 每日计划复盘
- [ ] 策略调整（如需要）

## 周任务

- [ ] 周一: 上周运营复盘报告
- [ ] 周五: 本周总结 + 下周计划

## 月任务

- [ ] 月末: 月度盈利目标达成报告

---

## 🔄 部署任务心跳监控

**文件：** `docs/deployment-progress.md`

### 每2小时检查一次

当 deployment-progress.md 显示仍有任务未完成时，自动继续执行：

**Phase 2 剩余任务（按顺序执行）：**
1. 统一import为shared模块
2. 删除冗余文件（按冗余分析报告）
3. 妙手登录方案实现

**Phase 3 测试验证：**
1. product-collector测试
2. listing-generator测试
3. product-uploader测试
4. miaoshou-uploader测试

**Phase 4 监控：**
1. 日志系统测试
2. 监控面板

### 执行逻辑

```
每2小时:
1. 读取 deployment-progress.md
2. 检查未完成任务
3. 按优先级继续执行
4. 更新进度文件
5. 如全部完成，发送通知
```

---

---

## 🔄 工作流健康巡检 (每2小时)

**脚本：** `scripts/workflow_health_check.sh`

**执行时间：** 每2小时执行一次

**检查内容：**
1. 前置条件检查（妙手Cookies、本地服务、SSH隧道）
2. 执行轻量级工作流测试
3. 结果推送到飞书群

**定时任务：**
```bash
0 */2 * * * /root/.openclaw/workspace-e-commerce/scripts/workflow_health_check.sh
```

---

## 🔄 开发循环心跳 (每10分钟)

**目的：** 持续迭代开发，发现问题→分析→修复→测试→记录

### 执行逻辑

```
每10分钟:
1. 读取任务队列 (docs/dev-task-queue.md)
2. 当前任务状态检查
3. 如果有待修复问题 → 分析并修复
4. 如果有测试失败 → 调试并重测
5. 如果任务完成 → 更新记录，下一个任务
6. 生成报告到 logs/last-notification.txt
7. 检查并发送飞书通知
```

### 飞书通知

**报告位置：** `logs/last-notification.txt`

**发送逻辑：** 心跳脚本生成报告后，检测到新报告时自动发送到飞书群

**群聊ID：** `oc_cdff9eb5f5c8bd8151d20a17be309c23`

### 当前开发任务

**collector-scraper 模块修复：**

| 任务 | 优先级 | 状态 |
|------|--------|------|
| 货源ID提取修复 | P0 | 🔄 进行中 |
| SKU数量修正（2→3）| P0 | 🔄 进行中 |
| 物流信息提取 | P1 | ⬜ 待处理 |
| 数据落库 product-storer | P1 | ⬜ 待处理 |

### 任务队列文件
`docs/dev-task-queue.md` - 当前开发任务队列

### 已知问题记录
`docs/collector-scraper-test-record.md` - 测试记录和已知问题

---

## 标签速查

- \[DATA\] 数据分析
- \[PLAN\] 运营计划
- \[AUTO\] 自动化工具
- \[REPORT\] 报告
- \[RISK\] 风险预警
- \[DEPLOY\] 部署任务
- \[DEV\] 开发任务
- \[FIX\] 修复任务
